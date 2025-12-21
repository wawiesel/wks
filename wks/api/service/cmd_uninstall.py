"""Service uninstall command - removes system service."""

from collections.abc import Iterator

from ..config.WKSConfig import WKSConfig
from ..StageResult import StageResult
from . import ServiceUninstallOutput
from .Service import Service


def cmd_uninstall() -> StageResult:
    """Uninstall system service."""

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
        if not Service.validate_backend_type(result_obj, backend_type, ServiceUninstallOutput, "uninstalled"):
            yield (1.0, "Complete")
            return

        # Import and instantiate backend implementation
        yield (0.4, "Initializing backend implementation...")
        try:
            # Uninstall via backend implementation
            yield (0.6, "Uninstalling service...")
            with Service(config.service) as service:
                result = service.uninstall_service()

            yield (1.0, "Complete")

            success = result["success"]
            if success:
                result_obj.result = "Service uninstalled successfully"
            else:
                result_obj.result = result["error"]

            result_obj.output = ServiceUninstallOutput(
                errors=[] if success else [result_obj.result],
                warnings=[],
                message=result_obj.result,
                uninstalled=success,
            ).model_dump(mode="python")
            result_obj.success = success
        except NotImplementedError as e:
            yield (1.0, "Complete")
            result_obj.result = f"Error: Service uninstallation not supported for backend '{backend_type}'"
            result_obj.output = ServiceUninstallOutput(
                errors=[str(e)],
                warnings=[],
                message=str(e),
                uninstalled=False,
            ).model_dump(mode="python")
            result_obj.success = False
        except Exception as e:
            yield (1.0, "Complete")
            result_obj.result = f"Error uninstalling service: {e}"
            result_obj.output = ServiceUninstallOutput(
                errors=[str(e)],
                warnings=[],
                message=str(e),
                uninstalled=False,
            ).model_dump(mode="python")
            result_obj.success = False

    return StageResult(
        announce="Uninstalling service...",
        progress_callback=do_work,
    )
