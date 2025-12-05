"""Monitor Typer app that registers all monitor commands."""

import typer

from ..base import handle_stage_result
from .cmd_check import cmd_check
from .cmd_filter_add import cmd_filter_add
from .cmd_filter_remove import cmd_filter_remove
from .cmd_filter_show import cmd_filter_show
from .cmd_priority_add import cmd_priority_add
from .cmd_priority_remove import cmd_priority_remove
from .cmd_priority_show import cmd_priority_show
from .cmd_status import cmd_status
from .cmd_sync import cmd_sync

monitor_app = typer.Typer(
    name="monitor",
    help="Monitor operations",
    pretty_exceptions_show_locals=False,
    pretty_exceptions_enable=False,
    context_settings={"help_option_names": ["-h", "--help"]},
    invoke_without_command=True,
)


@monitor_app.callback(invoke_without_command=True)
def monitor_callback(ctx: typer.Context) -> None:
    """Monitor operations - shows available commands."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help(), err=True)
        raise typer.Exit()


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

# Register commands with StageResult handler
monitor_app.command(name="status")(handle_stage_result(cmd_status))
monitor_app.command(name="check")(handle_stage_result(cmd_check))
monitor_app.command(name="sync")(handle_stage_result(cmd_sync))

# Filter subcommands
filter_app.command(name="show")(handle_stage_result(cmd_filter_show))
filter_app.command(name="add")(handle_stage_result(cmd_filter_add))
filter_app.command(name="remove")(handle_stage_result(cmd_filter_remove))

# Priority subcommands
priority_app.command(name="show")(handle_stage_result(cmd_priority_show))
priority_app.command(name="add")(handle_stage_result(cmd_priority_add))
priority_app.command(name="remove")(handle_stage_result(cmd_priority_remove))

# Attach sub-apps
monitor_app.add_typer(filter_app, name="filter")
monitor_app.add_typer(priority_app, name="priority")
