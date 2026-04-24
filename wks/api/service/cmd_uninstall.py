from collections.abc import Iterator

from ..config.StageResult import StageResult
from ..config.WKSConfig import WKSConfig
from . import ServiceUninstallOutput
from .Service import Service


def cmd_uninstall() -> StageResult:
    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        yield (0.1, "Loading configuration...")
        config = WKSConfig.load()

        yield (0.2, "Validating backend type...")
        backend_type = config.service.type
        if not Service.validate_backend_type(result_obj, backend_type, ServiceUninstallOutput, "uninstalled"):
            yield (1.0, "Complete")
            return

        yield (0.4, "Initializing backend implementation...")
        try:
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
