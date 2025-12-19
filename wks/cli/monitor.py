"""Monitor Typer app that registers all monitor commands."""

import typer

from wks.api.monitor.cmd_check import cmd_check
from wks.api.monitor.cmd_filter_add import cmd_filter_add
from wks.api.monitor.cmd_filter_remove import cmd_filter_remove
from wks.api.monitor.cmd_filter_show import cmd_filter_show
from wks.api.monitor.cmd_priority_add import cmd_priority_add
from wks.api.monitor.cmd_priority_remove import cmd_priority_remove
from wks.api.monitor.cmd_priority_show import cmd_priority_show
from wks.api.monitor.cmd_prune import cmd_prune
from wks.api.monitor.cmd_remote_detect import cmd_remote_detect
from wks.api.monitor.cmd_status import cmd_status
from wks.api.monitor.cmd_sync import cmd_sync
from wks.cli._handle_stage_result import handle_stage_result

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
    invoke_without_command=True,
)


@filter_app.callback(invoke_without_command=True)
def filter_callback(ctx: typer.Context) -> None:
    """Filter operations - shows available commands."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help(), err=True)
        raise typer.Exit()


priority_app = typer.Typer(
    name="priority",
    help="Manage priority directories",
    pretty_exceptions_show_locals=False,
    pretty_exceptions_enable=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)


remote_app = typer.Typer(
    name="remote",
    help="Manage remote integrations",
    pretty_exceptions_show_locals=False,
    pretty_exceptions_enable=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)


# Register commands with StageResult handler
def status_command() -> None:
    """Get filesystem monitoring status."""
    handle_stage_result(cmd_status)()


monitor_app.command(name="status")(status_command)


def check_command(path: str = typer.Argument(..., help="File or directory path to check")) -> None:
    """Check if a path would be monitored and calculate its priority."""
    handle_stage_result(cmd_check)(path)


def sync_command(
    path: str | None = typer.Argument(None, help="File or directory path to sync"),
    recursive: bool = typer.Option(False, "--recursive", help="Recursively process directory"),
) -> None:
    """Force update of file or directory into monitor database."""
    if path is None:
        typer.echo(typer.get_current_context().get_help(), err=True)  # type: ignore[attr-defined]
        raise typer.Exit(code=1)
    handle_stage_result(cmd_sync)(path, recursive)


def filter_show_command(
    list_name: str | None = typer.Argument(None, help="Name of list to show (leave empty to list available)"),
) -> None:
    """Get contents of a monitor configuration list or list available names."""
    handle_stage_result(cmd_filter_show)(list_name)


def filter_add_command(
    list_name: str = typer.Argument(..., help="Name of list to modify"),
    value: str = typer.Argument(..., help="Value to add"),
) -> None:
    """Add a value to a monitor configuration list."""
    handle_stage_result(cmd_filter_add)(list_name, value)


def filter_remove_command(
    list_name: str = typer.Argument(..., help="Name of list to modify"),
    value: str = typer.Argument(..., help="Value to remove"),
) -> None:
    """Remove a value from a monitor configuration list."""
    handle_stage_result(cmd_filter_remove)(list_name, value)


def priority_add_command(
    path: str = typer.Argument(..., help="Path to set priority for"),
    priority: float = typer.Argument(..., help="New priority of the path"),
) -> None:
    """Set or update priority for a priority directory."""
    handle_stage_result(cmd_priority_add)(path, priority)


def priority_remove_command(
    path: str = typer.Argument(..., help="Path to unmanage"),
) -> None:
    """Remove a priority directory."""
    handle_stage_result(cmd_priority_remove)(path)


monitor_app.command(name="check")(check_command)
monitor_app.command(name="sync")(sync_command)


def prune_command() -> None:
    """Remove stale entries for files that no longer exist."""
    handle_stage_result(cmd_prune)()


monitor_app.command(name="prune")(prune_command)

# Filter subcommands
filter_app.command(name="show")(filter_show_command)
filter_app.command(name="add")(filter_add_command)
filter_app.command(name="remove")(filter_remove_command)


# Priority subcommands
def priority_show_command() -> None:
    """List all priority directories."""
    handle_stage_result(cmd_priority_show)()


priority_app.command(name="show")(priority_show_command)
priority_app.command(name="add")(priority_add_command)
priority_app.command(name="add")(priority_add_command)
priority_app.command(name="remove")(priority_remove_command)


# Remote subcommands
def remote_detect_command() -> None:
    """Detect remote folders like OneDrive/SharePoint."""
    handle_stage_result(cmd_remote_detect)()


remote_app.command(name="detect")(remote_detect_command)

# Attach sub-apps
monitor_app.add_typer(filter_app, name="filter")
monitor_app.add_typer(priority_app, name="priority")
monitor_app.add_typer(remote_app, name="remote")
