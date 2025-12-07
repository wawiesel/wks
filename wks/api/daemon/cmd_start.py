"""Daemon start command - starts the daemon process."""

from collections.abc import Iterator

from ..base import StageResult
from .DaemonConfig import _BACKEND_REGISTRY
from ._start_helpers import (
    _get_daemon_impl,
    _start_directly,
    _start_via_service,
    _validate_backend_type,
    _validate_daemon_config,
)


def cmd_start() -> StageResult:
    """Start daemon process (idempotent - ensures daemon is running).

    Behavior:
    - **If service is installed and loaded**: Uses `launchctl kickstart -k`
      (kills and restarts process if running, starts if not running)
      - Note: The `-k` flag means this will restart if already running
    - **If service is installed but not loaded**: Bootstraps the service
      (loads plist into launchctl and starts it)
    - **If service is not installed**: Starts daemon directly as background process
      (creates lock file, runs in background)

    This command is idempotent - safe to run multiple times. If the daemon is already
    running, it will restart it (for service mode) or fail gracefully (for direct mode).

    Use this when you want to "ensure the daemon is running" without fully reloading
    the service configuration.
    """
    # Return StageResult immediately with announce, work happens in progress_callback
    def do_work(update_progress: Callable[[str, float], None], result_obj: StageResult) -> None:
        """Do the actual work - called by wrapper after announce is displayed.
        
        Updates result_obj.result, result_obj.output, and result_obj.success directly.
        """
        from ..base import StageResult
        from ..config.WKSConfig import WKSConfig
        
        update_progress("Loading configuration...", 0.1)
        config = WKSConfig.load()

        # Validate config
        is_valid, error_output = _validate_daemon_config(config)
        if not is_valid:
            result_obj.result = "Error: daemon configuration not found in config.json"
            result_obj.output = error_output
            result_obj.success = False
            return

        # Validate backend type
        update_progress("Validating backend...", 0.2)
        backend_type = config.daemon.type
        is_valid, error_output = _validate_backend_type(backend_type)
        if not is_valid:
            result_obj.result = f"Error: Unsupported daemon backend type: {backend_type!r} (supported: {list(_BACKEND_REGISTRY.keys())})"
            result_obj.output = error_output
            result_obj.success = False
            return

        # Get daemon implementation and start
        update_progress("Starting daemon...", 0.5)
        try:
            daemon_impl = _get_daemon_impl(backend_type, config)
            service_status = daemon_impl.get_service_status()

            if service_status.get("installed", False):
                update_progress("Starting via service manager...", 0.7)
                start_result = _start_via_service(daemon_impl, backend_type)
            else:
                update_progress("Starting directly...", 0.7)
                start_result = _start_directly(backend_type)

            update_progress("Complete", 1.0)
            result_obj.result = start_result["result_msg"]
            result_obj.output = start_result["output"]
            result_obj.success = start_result["success"]
        except NotImplementedError as e:
            result_obj.result = f"Error: Service start not supported for backend '{backend_type}'"
            result_obj.output = {"error": str(e)}
            result_obj.success = False
        except Exception as e:
            result_obj.result = f"Error starting daemon: {e}"
            result_obj.output = {"error": str(e)}
            result_obj.success = False

    return StageResult(
        announce="Starting daemon...",
        progress_callback=do_work,
        progress_total=1,
    )
