"""Service install command - installs daemon as system service."""

from collections.abc import Iterator
from pathlib import Path

from ..config.WKSConfig import WKSConfig
from ..StageResult import StageResult
from . import ServiceInstallOutput
from .Service import Service


def cmd_install(restrict_dir: Path | None = None) -> StageResult:
    """Install service as system service.

    Reads service configuration from config.json and installs appropriate service mechanism
    using the backend implementation.
    """

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
        if not Service.validate_backend_type(result_obj, backend_type, ServiceInstallOutput, "installed"):
            yield (1.0, "Complete")
            return

        # Import and instantiate backend implementation
        yield (0.4, "Initializing backend implementation...")
        try:
            # Install via backend implementation
            yield (0.6, "Installing service...")
            with Service(config.service) as service:
                result = service.install_service(restrict_dir=restrict_dir)

            yield (1.0, "Complete")
            result_obj.result = f"Service installed successfully (label: {result.get('label', 'unknown')})"
            result_obj.output = ServiceInstallOutput(
                errors=[],
                warnings=[],
                message=result_obj.result,
                installed=result.get("success", True),
            ).model_dump(mode="python")
            result_obj.success = result.get("success", True)
        except NotImplementedError as e:
            yield (1.0, "Complete")
            result_obj.result = f"Error: Service installation not supported for backend '{backend_type}'"
            result_obj.output = ServiceInstallOutput(
                errors=[str(e)],
                warnings=[],
                message=str(e),
                installed=False,
            ).model_dump(mode="python")
            result_obj.success = False
        except Exception as e:
            yield (1.0, "Complete")
            result_obj.result = f"Error installing service: {e}"
            result_obj.output = ServiceInstallOutput(
                errors=[str(e)],
                warnings=[],
                message=str(e),
                installed=False,
            ).model_dump(mode="python")
            result_obj.success = False

    return StageResult(
        announce="Installing daemon service...",
        progress_callback=do_work,
    )
