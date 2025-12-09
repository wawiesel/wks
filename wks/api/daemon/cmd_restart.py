"""Daemon restart command - restarts the daemon process."""

from collections.abc import Iterator

from ..StageResult import StageResult
from . import DaemonRestartOutput
from .cmd_start import cmd_start
from .cmd_stop import cmd_stop


def cmd_restart() -> StageResult:
    """Restart daemon with full service reload.

    Behavior:
    - **Always stops first**: Unloads service from launchctl (if service is installed)
      or kills direct process (if running directly)
    - **Then starts**: Reloads plist into launchctl and starts fresh (if service)
      or starts new background process (if direct)

    **Difference from 'start':**
    - **start**: Uses `launchctl kickstart -k` which kills/restarts the process but
      keeps the service loaded in launchctl (doesn't reload plist)
    - **restart**: Performs full `bootout` (unload) then `bootstrap` (reload plist),
      ensuring the service configuration is completely reloaded from the plist file

    **When to use:**
    - Use **restart** when you want to ensure the service is fully reloaded from the
      plist file (e.g., after plist changes, or to ensure clean state)
    - Use **start** for a simple "ensure running" operation (will restart process
      if running, but doesn't reload plist configuration)
    """
    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        """Do the actual work - generator that yields progress and updates result.

        Yields: (progress_percent: float, message: str) tuples
        Updates result_obj.result, result_obj.output, and result_obj.success before finishing.
        """
        # Stop first
        yield (0.2, "Stopping daemon...")
        stop_result = cmd_stop()
        stop_gen = stop_result.progress_callback(stop_result)
        list(stop_gen)  # Consume generator
        # Don't fail if stop fails - might not be running

        # Start
        yield (0.6, "Starting daemon...")
        start_result = cmd_start()
        start_gen = start_result.progress_callback(start_result)
        list(start_gen)  # Consume generator

        if not start_result.success:
            yield (1.0, "Complete")
            result_obj.result = start_result.result
            result_obj.output = DaemonRestartOutput(
                errors=start_result.output.get("errors", []),
                warnings=start_result.output.get("warnings", []),
                message=start_result.result,
                restarted=False,
            ).model_dump(mode="python")
            result_obj.success = False
            return

        yield (1.0, "Complete")
        result_obj.result = "Daemon restarted successfully"
        result_obj.output = DaemonRestartOutput(
            errors=[],
            warnings=[],
            message="Daemon restarted successfully",
            restarted=True,
        ).model_dump(mode="python")
        result_obj.success = True

    return StageResult(
        announce="Restarting daemon...",
        progress_callback=do_work,
    )
