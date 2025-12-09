"""Daemon stop command - stops the daemon process."""

from collections.abc import Iterator

from ..StageResult import StageResult
from ..config.WKSConfig import WKSConfig
from . import DaemonStopOutput
from .DaemonConfig import _BACKEND_REGISTRY


def cmd_stop() -> StageResult:
    """Stop daemon process."""
    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        """Do the actual work - generator that yields progress and updates result.

        Yields: (progress_percent: float, message: str) tuples
        Updates result_obj.result, result_obj.output, and result_obj.success before finishing.
        """
        yield (0.1, "Loading configuration...")
        config = WKSConfig.load()

        # Validate backend type
        yield (0.2, "Validating backend type...")
        backend_type = config.daemon.type
        if backend_type not in _BACKEND_REGISTRY:
            yield (1.0, "Complete")
            result_obj.result = f"Error: Unsupported daemon backend type: {backend_type!r} (supported: {list(_BACKEND_REGISTRY.keys())})"
            result_obj.output = normalize_output({
                "error": f"Unsupported backend type: {backend_type!r}",
                "supported": list(_BACKEND_REGISTRY.keys()),
            })
            result_obj.success = False
            return

        # Import and instantiate backend implementation
        yield (0.4, "Initializing backend implementation...")
        try:
            module = __import__(f"wks.api.daemon._{backend_type}._Impl", fromlist=[""])
            impl_class = module._Impl
            daemon_impl = impl_class(config.daemon)

            # Check if service is installed
            yield (0.5, "Checking service status...")
            service_status = daemon_impl.get_service_status()
            if not service_status.get("installed", False):
                yield (1.0, "Complete")
                result_obj.result = "Error: Daemon service not installed."
                result_obj.output = DaemonStopOutput(
                    errors=["service not installed"],
                    warnings=[],
                    message="service not installed",
                    stopped=False,
                ).model_dump(mode="python")
                result_obj.success = False
                return

            # Stop via service manager
            yield (0.7, "Stopping service...")
            result = daemon_impl.stop_service()
            yield (1.0, "Complete")
            if result.get("success", False):
                if "note" in result:
                    result_obj.result = f"Daemon is already stopped (label: {result.get('label', 'unknown')})"
                else:
                    result_obj.result = f"Daemon stopped successfully (label: {result.get('label', 'unknown')})"
            else:
                result_obj.result = f"Error stopping daemon: {result.get('error', 'unknown error')}"
            result_obj.output = DaemonStopOutput(
                errors=[result.get("error", "")] if not result.get("success", False) else [],
                warnings=[],
                message=result_obj.result,
                stopped=result.get("success", False),
            ).model_dump(mode="python")
            result_obj.success = result.get("success", False)
        except NotImplementedError as e:
            yield (1.0, "Complete")
            result_obj.result = f"Error: Service stop not supported for backend '{backend_type}'"
            result_obj.output = DaemonStopOutput(
                errors=[str(e)],
                warnings=[],
                message=str(e),
                stopped=False,
            ).model_dump(mode="python")
            result_obj.success = False
        except Exception as e:
            yield (1.0, "Complete")
            result_obj.result = f"Error stopping daemon: {e}"
            result_obj.output = DaemonStopOutput(
                errors=[str(e)],
                warnings=[],
                message=str(e),
                stopped=False,
            ).model_dump(mode="python")
            result_obj.success = False

    return StageResult(
        announce="Stopping daemon...",
        progress_callback=do_work,
    )
