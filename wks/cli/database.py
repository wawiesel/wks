"""Database Typer app that registers all database commands."""

import typer

from wks.cli.handle_stage_result import handle_stage_result
from wks.api.database.cmd_list import cmd_list
from wks.api.database.cmd_reset import cmd_reset
from wks.api.database.cmd_show import cmd_show

db_app = typer.Typer(
    name="database",
    help="Database operations",
    pretty_exceptions_show_locals=False,
    pretty_exceptions_enable=False,
    context_settings={"help_option_names": ["-h", "--help"]},
    invoke_without_command=True,
)


@db_app.callback(invoke_without_command=True)
def db_callback(ctx: typer.Context) -> None:
    """Database operations - shows available commands."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help(), err=True)
        raise typer.Exit()


# Register commands with StageResult handler
def show_command(
    ctx: typer.Context,
    database: str | None = typer.Argument(
        None,
        help="Database name (without prefix, e.g., 'monitor'). Use 'wksc database list' to find available databases.",
    ),
    query: str | None = typer.Option(None, "--query", "-q", help="Query filter as JSON string (MongoDB-style)"),
    limit: int = typer.Option(50, "--limit", "-l", help="Maximum number of documents to return"),
) -> None:
    """Show a database."""
    if database is None:
        typer.echo("Error: Database name is required", err=True)
        typer.echo(ctx.get_help(), err=True)
        raise typer.Exit(1)
    wrapped = handle_stage_result(cmd_show)
    wrapped(database, query, limit)


def reset_command(
    ctx: typer.Context,
    database: str | None = typer.Argument(
        None,
        help="Database name (without prefix, e.g., 'monitor'). Use 'wksc database list' to find available databases.",
    ),
) -> None:
    """Reset (clear) a database collection by deleting all documents."""
    if database is None:
        typer.echo("Error: Database name is required", err=True)
        typer.echo(ctx.get_help(), err=True)
        raise typer.Exit(1)
    wrapped = handle_stage_result(cmd_reset)
    wrapped(database)


db_app.command(name="list")(handle_stage_result(cmd_list))
db_app.command(name="reset")(reset_command)
db_app.command(name="show")(show_command)

