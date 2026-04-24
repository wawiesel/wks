from collections.abc import Iterator

from ..config.StageResult import StageResult
from . import McpListOutput
from .targets import list_targets


def cmd_list() -> StageResult:
    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        yield (0.4, "Collecting supported MCP targets...")
        targets = []
        for target in list_targets():
            targets.append(
                {
                    "name": target.name,
                    "description": target.description,
                    "install_command": target.install_command,
                    "uninstall_command": target.uninstall_command,
                }
            )

        yield (1.0, "Complete")
        result_obj.result = f"Found {len(targets)} supported MCP target(s)"
        result_obj.output = McpListOutput(
            targets=targets,
            count=len(targets),
            errors=[],
            warnings=[],
        ).model_dump(mode="python")
        result_obj.success = True

    return StageResult(
        announce="Listing supported MCP client targets...",
        progress_callback=do_work,
    )
