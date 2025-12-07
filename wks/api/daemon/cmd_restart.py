"""Daemon restart command - restarts the daemon process."""

from ..base import StageResult
from .cmd_stop import cmd_stop
from .cmd_start import cmd_start


def cmd_restart() -> StageResult:
    """Restart daemon process (stop then start)."""
    # Stop first
    stop_result = cmd_stop()
    if not stop_result.success:
        # If stop fails, try start anyway (might not be running)
        pass

    # Start
    start_result = cmd_start()
    if not start_result.success:
        return start_result

    return StageResult(
        announce="Restarting daemon...",
        result="Daemon restarted successfully",
        output={**start_result.output, "restarted": True},
        success=True,
    )

