"""DB Typer app that registers all database commands."""

import typer

from ..base import handle_stage_result
from .cmd_query import cmd_query

db_app = typer.Typer(
    name="db",
    help="Database operations",
    pretty_exceptions_show_locals=False,
    pretty_exceptions_enable=False,
    context_settings={"help_option_names": ["-h", "--help"]},
    invoke_without_command=True,
)


@db_app.callback(invoke_without_command=True)
def db_callback(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        from ...config import WKSConfig
        from .DbCollection import DbCollection
        try:
            config = WKSConfig.load()
            with DbCollection(config.db, "_") as collection:
                collection_names = sorted(collection._impl.list_collection_names())  # type: ignore[attr-defined]
        except Exception:
            collection_names = []

        if collection_names:
            typer.echo("Available collections:", err=True)
            for name in collection_names:
                typer.echo(f"  {name}", err=True)
            typer.echo(f"\nUse 'wksc db query <name>' to query a collection.", err=True)
        else:
            typer.echo("No collections found. Use 'wksc db query <name>' to query a collection.", err=True)
        raise typer.Exit()


# Register the query command - takes collection name as argument (prefix is auto-prepended from config)
db_app.command(name="query")(handle_stage_result(cmd_query))
