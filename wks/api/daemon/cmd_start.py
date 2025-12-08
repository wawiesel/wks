"""Daemon start command - starts the daemon process."""

from collections.abc import Iterator

from ..StageResult import StageResult
from .._normalize_output import normalize_output
from .DaemonConfig import _BACKEND_REGISTRY
from ._start_helpers import (
    _get_daemon_impl,
    _start_directly,
    _start_via_service,
    _validate_backend_type,
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
    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        """Do the actual work - generator that yields progress and updates result.

        Yields: (progress_percent: float, message: str) tuples
        Updates result_obj.result, result_obj.output, and result_obj.success before finishing.
        """
        from ..config.WKSConfig import WKSConfig

        yield (0.1, "Loading configuration...")
        config = WKSConfig.load()

        # Validate backend type
        yield (0.2, "Validating backend...")
        backend_type = config.daemon.type
        is_valid, error_output = _validate_backend_type(backend_type)
        if not is_valid:
            yield (1.0, "Complete")
            result_obj.result = f"Error: Unsupported daemon backend type: {backend_type!r} (supported: {list(_BACKEND_REGISTRY.keys())})"
            result_obj.output = normalize_output(error_output or {})
            result_obj.success = False
            return

        # Get daemon implementation and start
        yield (0.5, "Starting daemon...")
        try:
            daemon_impl = _get_daemon_impl(backend_type, config)
            service_status = daemon_impl.get_service_status()

            if service_status.get("installed", False):
                yield (0.7, "Starting via service manager...")
                start_result = _start_via_service(daemon_impl, backend_type)
            else:
                yield (0.7, "Starting directly...")
                start_result = _start_directly(backend_type)

            yield (1.0, "Complete")
            result_obj.result = start_result["result_msg"]
            result_obj.output = normalize_output(start_result["output"])
            result_obj.success = start_result["success"]
        except NotImplementedError as e:
            yield (1.0, "Complete")
            result_obj.result = f"Error: Service start not supported for backend '{backend_type}'"
            result_obj.output = normalize_output({"error": str(e)})
            result_obj.success = False
        except Exception as e:
            yield (1.0, "Complete")
            result_obj.result = f"Error starting daemon: {e}"
            result_obj.output = normalize_output({"error": str(e)})
            result_obj.success = False

    return StageResult(
        announce="Starting daemon...",
        progress_callback=do_work,
    )
