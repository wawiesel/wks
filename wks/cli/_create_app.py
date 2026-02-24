"""Create the main Typer CLI app."""

import typer

from wks.cli.cat import cat
from wks.cli.config import config
from wks.cli.daemon import daemon
from wks.cli.database import database
from wks.cli.diff import diff
from wks.cli.index import index
from wks.cli.link import link
from wks.cli.log import log
from wks.cli.mcp import mcp
from wks.cli.monitor import monitor
from wks.cli.mv import mv
from wks.cli.search import search
from wks.cli.service import service
from wks.cli.status import register_status
from wks.cli.transform import transform
from wks.cli.vault import vault


def _create_app() -> typer.Typer:
    """Create and configure the main CLI Typer app."""
    app = typer.Typer(
        pretty_exceptions_show_locals=False,
        pretty_exceptions_enable=False,
        help="WKS CLI",
        context_settings={"help_option_names": ["-h", "--help"]},
        invoke_without_command=True,
    )

    # Register all domain apps (call factory functions)
    app.add_typer(cat(), name="cat")
    app.add_typer(monitor(), name="monitor")
    app.add_typer(vault(), name="vault")
    app.add_typer(link(), name="link")
    app.add_typer(daemon(), name="daemon")
    app.add_typer(service(), name="service")
    app.add_typer(config(), name="config")
    app.add_typer(database(), name="database")
    app.add_typer(diff(), name="diff")
    app.add_typer(index(), name="index")
    app.add_typer(mcp(), name="mcp")
    app.add_typer(log(), name="log")
    app.add_typer(search(), name="search")
    register_status(app)
    app.add_typer(transform(), name="transform")
    app.add_typer(mv(), name="mv")

    @app.callback(invoke_without_command=True)
    def main_callback(
        ctx: typer.Context,
        display: str = typer.Option("yaml", "--display", "-d", help="Output format: json or yaml"),
        quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress progress output, emit data only"),
    ) -> None:
        # Validate display format
        display = display.lower()
        if display not in ("json", "yaml"):
            typer.echo(f"Error: --display must be 'json' or 'yaml', got '{display}'", err=True)
            raise typer.Exit(1)

        # Store settings in context for use by commands
        ctx.ensure_object(dict)
        if ctx.obj is None:
            ctx.obj = {}
        ctx.obj["display_format"] = display
        ctx.obj["quiet"] = quiet

        if ctx.invoked_subcommand is None:
            typer.echo(ctx.get_help())
            raise typer.Exit(2)

    return app
