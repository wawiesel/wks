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
    help="Manage priority directories",
    pretty_exceptions_show_locals=False,
    pretty_exceptions_enable=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)


# Register commands with StageResult handler
def check_command(
    ctx: typer.Context,
    path: str | None = typer.Argument(None, help="File or directory path to check"),
) -> None:
    """Check if a path would be monitored and calculate its priority."""
    if path is None:
        typer.echo("Error: Path is required", err=True)
        typer.echo(ctx.get_help(), err=True)
        raise typer.Exit(1)
    wrapped = handle_stage_result(cmd_check)
    wrapped(path)


def sync_command(
    ctx: typer.Context,
    path: str | None = typer.Argument(None, help="File or directory path to sync"),
    recursive: bool = typer.Option(False, "--recursive", help="Recursively process directory"),
) -> None:
    """Force update of file or directory into monitor database."""
    if path is None:
        typer.echo("Error: Path is required", err=True)
        typer.echo(ctx.get_help(), err=True)
        raise typer.Exit(1)
    wrapped = handle_stage_result(cmd_sync)
    wrapped(path, recursive)


def filter_show_command(
    ctx: typer.Context,
    list_name: str | None = typer.Argument(None, help="Name of list to show (leave empty to list available)"),
) -> None:
    """Get contents of a monitor configuration list or list available names."""
    wrapped = handle_stage_result(cmd_filter_show)
    wrapped(list_name)


def filter_add_command(
    ctx: typer.Context,
    list_name: str | None = typer.Argument(None, help="Name of list to modify"),
    value: str | None = typer.Argument(None, help="Value to add"),
) -> None:
    """Add a value to a monitor configuration list."""
    if list_name is None:
        typer.echo("Error: List name is required", err=True)
        typer.echo(ctx.get_help(), err=True)
        raise typer.Exit(1)
    if value is None:
        typer.echo("Error: Value is required", err=True)
        typer.echo(ctx.get_help(), err=True)
        raise typer.Exit(1)
    wrapped = handle_stage_result(cmd_filter_add)
    wrapped(list_name, value)


def filter_remove_command(
    ctx: typer.Context,
    list_name: str | None = typer.Argument(None, help="Name of list to modify"),
    value: str | None = typer.Argument(None, help="Value to remove"),
) -> None:
    """Remove a value from a monitor configuration list."""
    if list_name is None:
        typer.echo("Error: List name is required", err=True)
        typer.echo(ctx.get_help(), err=True)
        raise typer.Exit(1)
    if value is None:
        typer.echo("Error: Value is required", err=True)
        typer.echo(ctx.get_help(), err=True)
        raise typer.Exit(1)
    wrapped = handle_stage_result(cmd_filter_remove)
    wrapped(list_name, value)


def priority_add_command(
    ctx: typer.Context,
    path: str | None = typer.Argument(None, help="Path to set priority for"),
    priority: float | None = typer.Argument(None, help="New priority of the path"),
) -> None:
    """Set or update priority for a priority directory."""
    if path is None:
        typer.echo("Error: Path is required", err=True)
        typer.echo(ctx.get_help(), err=True)
        raise typer.Exit(1)
    if priority is None:
        typer.echo("Error: Priority is required", err=True)
        typer.echo(ctx.get_help(), err=True)
        raise typer.Exit(1)
    wrapped = handle_stage_result(cmd_priority_add)
    wrapped(path, priority)


def priority_remove_command(
    ctx: typer.Context,
    path: str | None = typer.Argument(None, help="Path to unmanage"),
) -> None:
    """Remove a priority directory."""
    if path is None:
        typer.echo("Error: Path is required", err=True)
        typer.echo(ctx.get_help(), err=True)
        raise typer.Exit(1)
    wrapped = handle_stage_result(cmd_priority_remove)
    wrapped(path)


monitor_app.command(name="status")(handle_stage_result(cmd_status))
monitor_app.command(name="check")(check_command)
monitor_app.command(name="sync")(sync_command)

# Filter subcommands
filter_app.command(name="show")(filter_show_command)
filter_app.command(name="add")(filter_add_command)
filter_app.command(name="remove")(filter_remove_command)

# Priority subcommands
priority_app.command(name="show")(handle_stage_result(cmd_priority_show))
priority_app.command(name="add")(priority_add_command)
priority_app.command(name="remove")(priority_remove_command)

# Attach sub-apps
monitor_app.add_typer(filter_app, name="filter")
monitor_app.add_typer(priority_app, name="priority")
