"""Service stop command - stops the service process."""

from collections.abc import Iterator

from ..config.StageResult import StageResult
from ..config.WKSConfig import WKSConfig
from . import ServiceStopOutput
from .Service import Service


def cmd_stop() -> StageResult:
    """Stop service process."""

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        """Do the actual work - generator that yields progress and updates result.

        Yields: (progress_percent: float, message: str) tuples
        Updates result_obj.result, result_obj.output, and result_obj.success before finishing.
        """
        yield (0.1, "Loading configuration...")
        config = WKSConfig.load()

        # Validate backend type
        yield (0.2, "Validating backend type...")
        backend_type = config.service.type
        if not Service.validate_backend_type(result_obj, backend_type, ServiceStopOutput, "stopped"):
            yield (1.0, "Complete")
            return

        # Import and instantiate backend implementation
        yield (0.4, "Initializing backend implementation...")
        try:
            with Service(config.service) as service:
                # Check if service is installed
                yield (0.5, "Checking service status...")
                service_status = service.get_service_status()

                if not service_status.installed:
                    yield (1.0, "Complete")
                    result_obj.result = "Error: Service not installed."
                    result_obj.output = ServiceStopOutput(
                        errors=["service not installed"],
                        warnings=[],
                        message="Service not installed",
                        stopped=False,
                    ).model_dump(mode="python")
                    result_obj.success = False
                    return

                # Stop via service manager
                yield (0.7, "Stopping service...")
                result = service.stop_service()
                yield (1.0, "Complete")
                if result["success"]:
                    if "note" in result:
                        result_obj.result = "Service is already stopped"
                    else:
                        result_obj.result = "Service stopped successfully"
                else:
                    result_obj.result = f"Error stopping service: {result['error']}"
                result_obj.output = ServiceStopOutput(
                    errors=[result["error"]] if not result["success"] else [],
                    warnings=[],
                    message=result_obj.result,
                    stopped=result["success"],
                ).model_dump(mode="python")
                result_obj.success = result["success"]
        except NotImplementedError as e:
            yield (1.0, "Complete")
            result_obj.result = f"Error: Service stop not supported for backend '{backend_type}'"
            result_obj.output = ServiceStopOutput(
                errors=[str(e)],
                warnings=[],
                message=str(e),
                stopped=False,
            ).model_dump(mode="python")
            result_obj.success = False
        except Exception as e:
            yield (1.0, "Complete")
            result_obj.result = f"Error stopping service: {e}"
            result_obj.output = ServiceStopOutput(
                errors=[str(e)],
                warnings=[],
                message=str(e),
                stopped=False,
            ).model_dump(mode="python")
            result_obj.success = False

    return StageResult(
        announce="Stopping service...",
        progress_callback=do_work,
    )
