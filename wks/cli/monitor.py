"""Monitor Typer app factory."""

import typer

from wks.api.monitor.cmd_check import cmd_check
from wks.api.monitor.cmd_filter_add import cmd_filter_add
from wks.api.monitor.cmd_filter_remove import cmd_filter_remove
from wks.api.monitor.cmd_filter_show import cmd_filter_show
from wks.api.monitor.cmd_priority_add import cmd_priority_add
from wks.api.monitor.cmd_priority_remove import cmd_priority_remove
from wks.api.monitor.cmd_priority_show import cmd_priority_show
from wks.api.monitor.cmd_status import cmd_status
from wks.api.monitor.cmd_sync import cmd_sync
from wks.cli._handle_stage_result import _handle_stage_result
from wks.cli._resolve_uri_arg import _resolve_uri_arg


def monitor() -> typer.Typer:
    """Create and configure the monitor Typer app."""
    app = typer.Typer(
        name="monitor",
        help="Monitor operations",
        pretty_exceptions_show_locals=False,
        pretty_exceptions_enable=False,
        context_settings={"help_option_names": ["-h", "--help"]},
        invoke_without_command=True,
    )

    @app.callback(invoke_without_command=True)
    def callback(ctx: typer.Context) -> None:
        """Monitor operations - shows available commands."""
        if ctx.invoked_subcommand is None:
            typer.echo(ctx.get_help(), err=True)
            raise typer.Exit()

    @app.command(name="status")
    def status_cmd() -> None:
        """Get filesystem monitoring status."""
        _handle_stage_result(cmd_status)()

    @app.command(name="check")
    def check_cmd(path: str = typer.Argument(..., help="File or directory path to check")) -> None:
        """Check if a path would be monitored and calculate its priority."""
        uri = _resolve_uri_arg(path)
        _handle_stage_result(cmd_check)(uri)

    @app.command(name="sync")
    def sync_cmd(
        path: str = typer.Argument(..., help="File or directory path to sync"),
        recursive: bool = typer.Option(False, "--recursive", help="Recursively process directory"),
    ) -> None:
        """Force update of file or directory into monitor database."""
        uri = _resolve_uri_arg(path)
        _handle_stage_result(cmd_sync)(uri, recursive)

    # Sub-app for filter commands
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

    @filter_app.command(name="show")
    def filter_show_cmd(
        list_name: str | None = typer.Argument(None, help="Name of list to show (leave empty to list available)"),
    ) -> None:
        """Get contents of a monitor configuration list or list available names."""
        _handle_stage_result(cmd_filter_show)(list_name)

    @filter_app.command(name="add")
    def filter_add_cmd(
        list_name: str = typer.Argument(..., help="Name of list to modify"),
        value: str = typer.Argument(..., help="Value to add"),
    ) -> None:
        """Add a value to a monitor configuration list."""
        _handle_stage_result(cmd_filter_add)(list_name, value)

    @filter_app.command(name="remove")
    def filter_remove_cmd(
        list_name: str = typer.Argument(..., help="Name of list to modify"),
        value: str = typer.Argument(..., help="Value to remove"),
    ) -> None:
        """Remove a value from a monitor configuration list."""
        _handle_stage_result(cmd_filter_remove)(list_name, value)

    # Sub-app for priority commands
    priority_app = typer.Typer(
        name="priority",
        help="Manage priority directories",
        pretty_exceptions_show_locals=False,
        pretty_exceptions_enable=False,
        context_settings={"help_option_names": ["-h", "--help"]},
        invoke_without_command=True,
    )

    @priority_app.callback(invoke_without_command=True)
    def priority_callback(ctx: typer.Context) -> None:
        """Priority operations - shows available commands."""
        if ctx.invoked_subcommand is None:
            typer.echo(ctx.get_help(), err=True)
            raise typer.Exit()

    @priority_app.command(name="show")
    def priority_show_cmd() -> None:
        """List all priority directories."""
        _handle_stage_result(cmd_priority_show)()

    @priority_app.command(name="add")
    def priority_add_cmd(
        path: str = typer.Argument(..., help="Path to set priority for"),
        priority: float = typer.Argument(..., help="New priority of the path"),
    ) -> None:
        """Set or update priority for a priority directory."""
        _handle_stage_result(cmd_priority_add)(path, priority)

    @priority_app.command(name="remove")
    def priority_remove_cmd(
        path: str = typer.Argument(..., help="Path to unmanage"),
    ) -> None:
        """Remove a priority directory."""
        _handle_stage_result(cmd_priority_remove)(path)

    # Attach sub-apps
    app.add_typer(filter_app, name="filter")
    app.add_typer(priority_app, name="priority")

    return app
