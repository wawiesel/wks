"""Daemon reinstall command - uninstalls if exists, then installs."""

from collections.abc import Iterator

from ..StageResult import StageResult
from .._normalize_output import normalize_output
from ..config.WKSConfig import WKSConfig
from .DaemonConfig import _BACKEND_REGISTRY
from .cmd_install import cmd_install
from .cmd_uninstall import cmd_uninstall


def cmd_reinstall() -> StageResult:
    """Reinstall daemon service - uninstalls if exists, then installs."""
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

        # Check if service is installed
        yield (0.3, "Checking if service is installed...")
        try:
            module = __import__(f"wks.api.daemon._{backend_type}._Impl", fromlist=[""])
            impl_class = module._Impl
            daemon_impl = impl_class(config.daemon)
            service_status = daemon_impl.get_service_status()
            is_installed = service_status.get("installed", False)
        except Exception:
            is_installed = False

        # Uninstall if installed
        if is_installed:
            yield (0.4, "Uninstalling existing service...")
            uninstall_result = cmd_uninstall()
            # Execute uninstall
            uninstall_gen = uninstall_result.progress_callback(uninstall_result)
            list(uninstall_gen)  # Consume generator
            if not uninstall_result.success:
                yield (1.0, "Complete")
                result_obj.result = f"Failed to uninstall existing service: {uninstall_result.result}"
                result_obj.output = uninstall_result.output
                result_obj.success = False
                return
        else:
            yield (0.4, "No existing service to uninstall...")

        # Install
        yield (0.6, "Installing service...")
        install_result = cmd_install()
        # Execute install
        install_gen = install_result.progress_callback(install_result)
        list(install_gen)  # Consume generator

        yield (1.0, "Complete")
        result_obj.result = install_result.result
        result_obj.output = install_result.output
        result_obj.success = install_result.success

    return StageResult(
        announce="Reinstalling daemon service...",
        progress_callback=do_work,
    )
