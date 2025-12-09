"""Daemon start command - starts the daemon process."""

from collections.abc import Iterator

from ..StageResult import StageResult
from . import DaemonStartOutput
from .Daemon import Daemon


def cmd_start() -> StageResult:
    """Start daemon via system service manager.

    Behavior:
    - **If service is installed and loaded**: Uses `launchctl kickstart -k`
      (kills and restarts process if running, starts if not running)
      - Note: The `-k` flag means this will restart if already running
    - **If service is installed but not loaded**: Bootstraps the service
      (loads plist into launchctl and starts it)
    - **If service is not installed**: Fails with an error (use `wksc daemon run` to run without a service)

    This command is idempotent - safe to run multiple times. If the daemon is already
    running, it will restart it.

    Use this when you want to "ensure the daemon service is running" without fully reloading
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
        if not Daemon._validate_backend_type(result_obj, backend_type, DaemonStartOutput, "running"):
            yield (1.0, "Complete")
            return

        # Get daemon implementation and start
        yield (0.5, "Starting daemon...")
        try:
            with Daemon(config.daemon) as daemon:
                service_status = daemon.get_service_status()
                if "installed" not in service_status:
                    raise KeyError("get_service_status() result missing required 'installed' field")

                if not service_status["installed"]:
                    yield (1.0, "Complete")
                    error_msg = "Service is not installed. Use 'wksc daemon install' to install the service, or 'wksc daemon run' to run without a service."
                    result_obj.result = f"Error: {error_msg}"
                    result_obj.output = DaemonStartOutput(
                        errors=[error_msg],
                        warnings=[],
                        message=error_msg,
                        running=False,
                    ).model_dump(mode="python")
                    result_obj.success = False
                    return

                yield (0.7, "Starting via service manager...")
                start_result = daemon._start_via_service()

            yield (1.0, "Complete")
            result_obj.result = start_result.message
            result_obj.output = start_result.model_dump(mode="python")
            result_obj.success = start_result.running
        except NotImplementedError as e:
            yield (1.0, "Complete")
            result_obj.result = f"Error: Service start not supported for backend '{backend_type}'"
            result_obj.output = DaemonStartOutput(
                errors=[str(e)],
                warnings=[],
                message=str(e),
                running=False,
            ).model_dump(mode="python")
            result_obj.success = False
        except Exception as e:
            yield (1.0, "Complete")
            result_obj.result = f"Error starting daemon: {e}"
            result_obj.output = DaemonStartOutput(
                errors=[str(e)],
                warnings=[],
                message=str(e),
                running=False,
            ).model_dump(mode="python")
            result_obj.success = False

    return StageResult(
        announce="Starting daemon...",
        progress_callback=do_work,
    )
