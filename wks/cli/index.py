"""Index Typer app factory."""

import typer

from wks.api.index.cmd import cmd
from wks.api.index.cmd_backfill import cmd_backfill
from wks.api.index.cmd_embed import cmd_embed
from wks.api.index.cmd_status import cmd_status
from wks.cli._app_factory import build_typer_app, require_subcommand
from wks.cli._handle_stage_result import _handle_stage_result


def index() -> typer.Typer:
    """Create and configure the index Typer app."""
    app = build_typer_app(name="index", help_text="Add documents to a named index")
    require_subcommand(app, err=False)

    @app.command(name="add")
    def add_cmd(
        name: str = typer.Argument(..., help="Index name"),
        uri: str = typer.Argument(..., help="URI or file path to index"),
    ) -> None:
        """Add a document to a named index."""
        _handle_stage_result(cmd)(name, uri)

    @app.command(name="status")
    def status_cmd(
        name: str = typer.Argument("", help="Index name (all indexes if omitted)"),
    ) -> None:
        """Show index statistics."""
        _handle_stage_result(cmd_status)(name)

    @app.command(name="backfill")
    def backfill_cmd(
        name: str = typer.Argument("", help="Index name (uses default index if omitted)"),
    ) -> None:
        """Index all monitored files meeting the index's min_priority threshold."""
        _handle_stage_result(cmd_backfill)(name=name)

    @app.command(name="embed")
    def embed_cmd(
        name: str = typer.Argument("", help="Index name (uses default index if omitted)"),
        batch_size: int = typer.Option(64, "--batch-size", help="Embedding batch size"),
    ) -> None:
        """Build embeddings for a named index."""
        _handle_stage_result(cmd_embed)(name=name, batch_size=batch_size)

    return app
