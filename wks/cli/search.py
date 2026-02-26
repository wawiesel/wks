"""Search Typer app factory."""

from typing import Annotated

import typer

from wks.api.search.cmd import cmd
from wks.cli._handle_stage_result import _handle_stage_result


def search() -> typer.Typer:
    """Create and configure the search Typer app."""
    app = typer.Typer(
        name="search",
        help="Search indexed documents",
        pretty_exceptions_show_locals=False,
        pretty_exceptions_enable=False,
        context_settings={"help_option_names": ["-h", "--help"], "allow_interspersed_args": True},
        invoke_without_command=True,
    )

    @app.callback(invoke_without_command=True)
    def callback(
        ctx: typer.Context,
        query: Annotated[str | None, typer.Argument(help="Search query")] = None,
        query_image: Annotated[
            str,
            typer.Option(
                "--query-image",
                help="Image path or URI for semantic image search (requires semantic image-text index)",
            ),
        ] = "",
        index: Annotated[str, typer.Option("--index", "-i", help="Index name (uses default from config)")] = "",
        k: Annotated[int, typer.Option("--top", "-k", help="Number of results")] = 10,
    ) -> None:
        if (query is None or not query.strip()) and not query_image.strip():
            typer.echo(ctx.get_help(), err=True)
            raise typer.Exit(2)
        _handle_stage_result(cmd)(query or "", index=index, k=k, query_image=query_image)

    return app
