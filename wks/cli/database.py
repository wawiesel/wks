"""Database Typer app factory."""

import typer

from wks.api.database.cmd_list import cmd_list
from wks.api.database.cmd_prune import cmd_prune
from wks.api.database.cmd_reset import cmd_reset
from wks.api.database.cmd_show import cmd_show
from wks.cli._handle_stage_result import _handle_stage_result


def database() -> typer.Typer:
    """Create and configure the database Typer app."""
    app = typer.Typer(
        name="database",
        help="Database operations",
        pretty_exceptions_show_locals=False,
        pretty_exceptions_enable=False,
        context_settings={"help_option_names": ["-h", "--help"]},
        invoke_without_command=True,
    )

    @app.callback(invoke_without_command=True)
    def callback(ctx: typer.Context) -> None:
        if ctx.invoked_subcommand is None:
            typer.echo(ctx.get_help(), err=True)
            raise typer.Exit(2)

    @app.command(name="list")
    def list_cmd() -> None:
        """List all available databases."""
        _handle_stage_result(cmd_list)()

    @app.command(name="show")
    def show_cmd(
        name: str = typer.Argument(..., help="Database name (use 'list' for options)"),
        query: str | None = typer.Option(None, "--query", "-q", help="MongoDB-style query filter"),
        limit: int = typer.Option(50, "--limit", "-l", help="Max documents to return"),
    ) -> None:
        """Show database contents."""
        _handle_stage_result(cmd_show)(name, query, limit)

    @app.command(name="reset")
    def reset_cmd(
        name: str = typer.Argument(..., help="Database name (use 'list' for options)"),
        yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    ) -> None:
        """Reset (clear) a database by deleting all documents."""
        if not yes:
            typer.confirm(f"This will delete ALL documents from '{name}'. Continue?", abort=True)
        _handle_stage_result(cmd_reset)(name)

    @app.command(name="prune")
    def prune_cmd(
        name: str = typer.Argument(..., help="Database to prune ('all' or use 'list')"),
        remote: bool = typer.Option(False, "--remote", help="Check remote targets"),
    ) -> None:
        """Prune stale entries (e.g., files not found)."""
        _handle_stage_result(cmd_prune)(database=name.lower(), remote=remote)

    return app
