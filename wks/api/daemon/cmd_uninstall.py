"""Daemon uninstall command - removes daemon system service."""

from collections.abc import Iterator

from ..StageResult import StageResult
from ..config.WKSConfig import WKSConfig
from . import DaemonUninstallOutput
from .DaemonConfig import _BACKEND_REGISTRY


def cmd_uninstall() -> StageResult:
    """Uninstall daemon system service."""
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

            # Uninstall via backend implementation
            yield (0.6, "Uninstalling service...")
            result = daemon_impl.uninstall_service()
            # Remove 'success' from output - it's handled by StageResult.success
            output = {k: v for k, v in result.items() if k != "success"}

            yield (1.0, "Complete")
            result_obj.result = f"Daemon service uninstalled successfully (label: {result.get('label', 'unknown')})"
            result_obj.output = DaemonUninstallOutput(
                errors=[],
                warnings=[],
                message=result_obj.result,
                uninstalled=result.get("success", True),
            ).model_dump(mode="python")
            result_obj.success = result.get("success", True)
        except NotImplementedError as e:
            yield (1.0, "Complete")
            result_obj.result = f"Error: Service uninstallation not supported for backend '{backend_type}'"
            result_obj.output = DaemonUninstallOutput(
                errors=[str(e)],
                warnings=[],
                message=str(e),
                uninstalled=False,
            ).model_dump(mode="python")
            result_obj.success = False
        except Exception as e:
            yield (1.0, "Complete")
            result_obj.result = f"Error uninstalling service: {e}"
            result_obj.output = DaemonUninstallOutput(
                errors=[str(e)],
                warnings=[],
                message=str(e),
                uninstalled=False,
            ).model_dump(mode="python")
            result_obj.success = False

    return StageResult(
        announce="Uninstalling daemon service...",
        progress_callback=do_work,
    )
