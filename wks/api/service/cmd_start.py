from collections.abc import Iterator

from ..config.StageResult import StageResult
from . import ServiceStartOutput
from .Service import Service


def cmd_start() -> StageResult:
    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        from ..config.WKSConfig import WKSConfig

        yield (0.1, "Loading configuration...")
        config = WKSConfig.load()

        yield (0.2, "Validating backend...")
        backend_type = config.service.type
        if not Service.validate_backend_type(result_obj, backend_type, ServiceStartOutput, "running"):
            yield (1.0, "Complete")
            return

        yield (0.5, "Starting service...")
        try:
            with Service(config.service) as service:
                service_status = service.get_service_status()

                if not service_status.installed:
                    yield (1.0, "Complete")
                    error_msg = (
                        "Service is not installed. Use 'wksc service install' to install the service, "
                        "or 'wksc daemon run' to run without a service."
                    )
                    result_obj.result = f"Error: {error_msg}"
                    result_obj.output = ServiceStartOutput(
                        errors=[error_msg],
                        warnings=[],
                        message=error_msg,
                        running=False,
                    ).model_dump(mode="python")
                    result_obj.success = False
                    return

                was_running = service_status.running and service_status.pid is not None

                yield (0.7, "Starting via service manager...")
                start_result = service.start_via_service()

            yield (1.0, "Complete")
            if was_running and start_result.running:
                start_result.warnings.append(f"Service was already running (PID {service_status.pid}), restarted")
                start_result.message = f"Service restarted (was already running, PID {service_status.pid})"
            result_obj.result = start_result.message
            result_obj.output = start_result.model_dump(mode="python")
            result_obj.success = start_result.running
        except NotImplementedError as e:
            yield (1.0, "Complete")
            result_obj.result = f"Error: Service start not supported for backend '{backend_type}'"
            result_obj.output = ServiceStartOutput(
                errors=[str(e)],
                warnings=[],
                message=str(e),
                running=False,
            ).model_dump(mode="python")
            result_obj.success = False
        except Exception as e:
            yield (1.0, "Complete")
            result_obj.result = f"Error starting service: {e}"
            result_obj.output = ServiceStartOutput(
                errors=[str(e)],
                warnings=[],
                message=str(e),
                running=False,
            ).model_dump(mode="python")
            result_obj.success = False

    return StageResult(
        announce="Starting service...",
        progress_callback=do_work,
    )
