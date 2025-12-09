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
# Direct registration - Typer handles required argument validation via typer.Argument(...)
db_app.command(name="list")(handle_stage_result(cmd_list))


def show_command(
    database: str = typer.Argument(
        ...,
        help="Database name (without prefix, e.g., 'monitor'). Use 'wksc database list' to find available databases.",
    ),
    query: str | None = typer.Option(None, "--query", "-q", help="Query filter as JSON string (MongoDB-style)"),
    limit: int = typer.Option(50, "--limit", "-l", help="Maximum number of documents to return"),
) -> None:
    """Show a database."""
    handle_stage_result(cmd_show)(database, query, limit)


def reset_command(
    database: str = typer.Argument(
        ...,
        help="Database name (without prefix, e.g., 'monitor'). Use 'wksc database list' to find available databases.",
    ),
) -> None:
    """Reset (clear) a database collection by deleting all documents."""
    handle_stage_result(cmd_reset)(database)


db_app.command(name="show")(show_command)
db_app.command(name="reset")(reset_command)

