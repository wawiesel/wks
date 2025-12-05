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
    """Database operations - shows available database names."""
    if ctx.invoked_subcommand is None:
        from ...config import WKSConfig

        try:
            config = WKSConfig.load()
            db_config = config.db
            db_type = db_config.type

            # Load the appropriate client implementation based on db type
            if db_type == "mongo":
                from ._mongo.client import connect
                from ._mongo.MongoDbConfigData import MongoDbConfigData
                if not isinstance(db_config.data, MongoDbConfigData):
                    raise ValueError("MongoDB config data is required")
                uri = db_config.data.uri
            elif db_type == "mockmongo":
                from ._mockmongo.client import connect
                from ._mockmongo.MockMongoDbConfigData import MockMongoDbConfigData
                if not isinstance(db_config.data, MockMongoDbConfigData):
                    raise ValueError("MockMongoDB config data is required")
                uri = db_config.data.uri
            else:
                raise ValueError(f"Unsupported database type: {db_type}")

            # Query all collections in the "wks" database
            # Collections are named like "monitor", "vault", "transform" (accessed as "wks.monitor", etc.)
            client = connect(uri)
            try:
                wks_db = client["wks"]
                collection_names = sorted(wks_db.list_collection_names())
            finally:
                client.close()
        except Exception:
            # Fallback to empty list if we can't connect
            collection_names = []

        if collection_names:
            typer.echo("Available databases:", err=True)
            for name in collection_names:
                typer.echo(f"  {name} (accessed as wks.{name})", err=True)
            typer.echo("\nUse 'wksc db query <name>' to query a database.", err=True)
        else:
            typer.echo("No databases found. Use 'wksc db query <name>' to query a database.", err=True)
        raise typer.Exit()


# Register the query command - takes collection name as argument (e.g., "monitor" becomes "wks.monitor")
db_app.command(name="query")(handle_stage_result(cmd_query))
