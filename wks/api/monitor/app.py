"""Monitor Typer app that registers all monitor commands."""

import functools
import sys
from collections.abc import Callable

import typer

from ...display.cli import CLIDisplay
from ...display.context import get_display
from ..base import StageResult
from .cmd_check import cmd_check
from .cmd_filter_show import cmd_filter_show
from .cmd_filter_add import cmd_filter_add
from .cmd_filter_remove import cmd_filter_remove
from .cmd_priority_show import cmd_priority_show
from .cmd_priority_remove import cmd_priority_remove
from .cmd_priority_add import cmd_priority_add
from .cmd_status import cmd_status
from .cmd_sync import cmd_sync

monitor_app = typer.Typer(
    name="monitor",
    help="Monitor operations",
    pretty_exceptions_show_locals=False,
    pretty_exceptions_enable=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)

# Sub-apps for filter and priority
filter_app = typer.Typer(
    name="filter",
    help="Manage include/exclude rules",
    pretty_exceptions_show_locals=False,
    pretty_exceptions_enable=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)

priority_app = typer.Typer(
    name="priority",
    help="Manage managed_directories priority",
    pretty_exceptions_show_locals=False,
    pretty_exceptions_enable=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)


def _handle_stage_result(func: Callable) -> Callable:
    """Wrapper to handle StageResult and implement 4-stage pattern for CLI."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)

        # If result is not a StageResult, return as-is (for backward compatibility)
        if not isinstance(result, StageResult):
            return result

        display = get_display("cli")
        is_cli = isinstance(display, CLIDisplay)

        if is_cli:
            # Step 1: Announce
            display.status(result.announce)

            # Step 2: Progress
            total = result.progress_total if result.progress_total else 1
            if result.progress_callback:
                completed = 0

                def progress_update(description: str, progress: float):
                    nonlocal completed
                    target = max(int(progress * total), completed)
                    advance = max(target - completed, 0)
                    completed = target
                    progress_context.update(advance=advance or 0, description=description)

                with display.progress(total=total, description="Processing...") as progress_context:  # type: ignore[attr-defined]
                    result.progress_callback(progress_update)
            else:
                # Simple progress for instant operations
                with display.progress(total=1, description="Processing..."):  # type: ignore[attr-defined]
                    pass

            # Recompute success after work is done
            if isinstance(result.output, dict):
                result.success = result.output.get("success", result.success)
                if "message" in result.output:
                    result.result = str(result.output["message"])

            # Step 3: Result
            if result.success:
                display.success(result.result)
            else:
                display.error(result.result)

            # Step 4: Output
            # Automatically convert any data structure to tables for CLI display
            from ...display.format import data_to_tables

            output = result.output
            tables = data_to_tables(output)

            # Only show tables if there's actual data to display
            # Simple operations (managed-add, managed-remove, managed-set-priority)
            # typically return simple success dicts - skip output if it's just status info
            if tables:
                # Skip output if it's just a simple success/message dict
                if len(tables) == 1:
                    table_data = tables[0]
                    # If it's just success/message fields, skip (already shown in Step 3)
                    if table_data.get("headers") == ["Key", "Value"]:
                        data_keys = {row.get("Key") for row in table_data.get("data", [])}
                        if data_keys.issubset(
                            {
                                "success",
                                "message",
                                "path_stored",
                                "path_removed",
                                "old_priority",
                                "new_priority",
                                "already_exists",
                                "not_found",
                            }
                        ):
                            # Simple status dict - skip output
                            pass
                        else:
                            # Has additional data - show table
                            display.table(
                                table_data["data"],
                                headers=table_data.get("headers"),
                                title=table_data.get("title"),
                            )
                    else:
                        # Not a simple key-value table - show it
                        display.table(
                            table_data["data"],
                            headers=table_data.get("headers"),
                            title=table_data.get("title"),
                        )
                else:
                    # Multiple tables - show all
                    for table_data in tables:
                        display.table(
                            table_data["data"],
                            headers=table_data.get("headers"),
                            title=table_data.get("title"),
                        )

            # Exit with appropriate code
            sys.exit(0 if result.success else 1)
        else:
            # MCP: Execute work if needed then return output data directly
            if result.progress_callback:
                result.progress_callback(lambda *_args, **_kwargs: None)
                if isinstance(result.output, dict):
                    result.success = result.output.get("success", result.success)
            return result.output

    return wrapper


# Register commands with StageResult handler
monitor_app.command(name="status")(_handle_stage_result(cmd_status))
monitor_app.command(name="check")(_handle_stage_result(cmd_check))
monitor_app.command(name="sync")(_handle_stage_result(cmd_sync))

# Filter subcommands
filter_app.command(name="show")(_handle_stage_result(cmd_filter_show))
filter_app.command(name="add")(_handle_stage_result(cmd_filter_add))
filter_app.command(name="remove")(_handle_stage_result(cmd_filter_remove))

# Priority subcommands
priority_app.command(name="show")(_handle_stage_result(cmd_priority_show))
priority_app.command(name="add")(_handle_stage_result(cmd_priority_add))
priority_app.command(name="remove")(_handle_stage_result(cmd_priority_remove))

# Attach sub-apps
monitor_app.add_typer(filter_app, name="filter")
monitor_app.add_typer(priority_app, name="priority")
