"""Show the native install command for an MCP client target."""

from collections.abc import Iterator

from ..config.StageResult import StageResult
from . import McpInstallOutput
from .targets import get_target, target_names


def cmd_install(name: str) -> StageResult:
    """Show the native install command for a supported target.

    Args:
        name: Supported MCP client target name

    Returns:
        StageResult with the native client command to run
    """

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        """Resolve the target and report its native install command."""
        yield (0.4, "Resolving target...")
        target = get_target(name)
        if target is None:
            yield (1.0, "Complete")
            valid_targets = ", ".join(target_names())
            result_obj.result = f"Unsupported MCP target '{name}'. Supported targets: {valid_targets}"
            result_obj.output = McpInstallOutput(
                success=False,
                name=name,
                command="",
                errors=[f"Unsupported MCP target '{name}'"],
                warnings=[f"Supported targets: {valid_targets}"],
            ).model_dump(mode="python")
            result_obj.success = False
            return

        yield (1.0, "Complete")
        result_obj.result = f"Run the native client command to install WKS for '{name}'"
        result_obj.output = McpInstallOutput(
            success=True,
            name=target.name,
            command=target.install_command,
            errors=[],
            warnings=["WKS does not edit client config directly. Run the reported native client command yourself."],
        ).model_dump(mode="python")
        result_obj.success = True

    return StageResult(
        announce=f"Showing native install command for '{name}'...",
        progress_callback=do_work,
    )
