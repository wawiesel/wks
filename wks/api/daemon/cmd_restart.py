"""Daemon restart command - restarts the daemon process."""

from ..base import StageResult
from .cmd_stop import cmd_stop
from .cmd_start import cmd_start


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

