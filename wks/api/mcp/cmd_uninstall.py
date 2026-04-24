from collections.abc import Iterator

from ..config.StageResult import StageResult
from . import McpUninstallOutput
from .targets import get_target, target_names


def cmd_uninstall(name: str) -> StageResult:
    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        yield (0.4, "Resolving target...")
        target = get_target(name)
        if target is None:
            yield (1.0, "Complete")
            valid_targets = ", ".join(target_names())
            result_obj.result = f"Unsupported MCP target '{name}'. Supported targets: {valid_targets}"
            result_obj.output = McpUninstallOutput(
                success=False,
                name=name,
                command="",
                errors=[f"Unsupported MCP target '{name}'"],
                warnings=[f"Supported targets: {valid_targets}"],
            ).model_dump(mode="python")
            result_obj.success = False
            return

        yield (1.0, "Complete")
        result_obj.result = f"Run the native client command to uninstall WKS for '{name}'"
        result_obj.output = McpUninstallOutput(
            success=True,
            name=target.name,
            command=target.uninstall_command,
            errors=[],
            warnings=["WKS does not edit client config directly. Run the reported native client command yourself."],
        ).model_dump(mode="python")
        result_obj.success = True

    return StageResult(
        announce=f"Showing native uninstall command for '{name}'...",
        progress_callback=do_work,
    )
