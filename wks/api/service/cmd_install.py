from collections.abc import Iterator
from pathlib import Path

from ..config.StageResult import StageResult
from ..config.WKSConfig import WKSConfig
from . import ServiceInstallOutput
from .Service import Service


def cmd_install(restrict_dir: Path | None = None) -> StageResult:
    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        yield (0.1, "Loading configuration...")
        config = WKSConfig.load()

        yield (0.2, "Validating backend type...")
        backend_type = config.service.type
        if not Service.validate_backend_type(result_obj, backend_type, ServiceInstallOutput, "installed"):
            yield (1.0, "Complete")
            return

        yield (0.4, "Initializing backend implementation...")
        try:
            yield (0.6, "Installing service...")
            with Service(config.service) as service:
                result = service.install_service(restrict_dir=restrict_dir)

            yield (1.0, "Complete")
            if result["success"]:
                result_obj.result = "Service installed successfully"
            else:
                result_obj.result = result["error"]

            result_obj.output = ServiceInstallOutput(
                errors=[] if result["success"] else [result_obj.result],
                warnings=[],
                message=result_obj.result,
                installed=result["success"],
            ).model_dump(mode="python")
            result_obj.success = result["success"]
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
