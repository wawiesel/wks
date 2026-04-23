"""Similar Typer app factory."""

from typing import Annotated

import typer

from wks.api.similar.cmd import cmd
from wks.cli._handle_stage_result import _handle_stage_result


def similar() -> typer.Typer:
    """Create and configure the similar Typer app."""
    app = typer.Typer(
        name="similar",
        help="Find similar documents from semantic chunk matches",
        pretty_exceptions_show_locals=False,
        pretty_exceptions_enable=False,
        context_settings={"help_option_names": ["-h", "--help"], "allow_interspersed_args": True},
        invoke_without_command=True,
    )

    @app.callback(invoke_without_command=True)
    def callback(
        target: Annotated[str, typer.Argument(help="File or URI to compare against indexed documents")],
        index: Annotated[str | None, typer.Option("--index", "-i", help="Semantic index name")] = None,
        top: Annotated[int | None, typer.Option("--top", "-k", help="Number of results to return")] = None,
        per_chunk: Annotated[
            int | None,
            typer.Option("--per-chunk", help="Unique candidate docs to seed per query chunk"),
        ] = None,
        candidates: Annotated[int | None, typer.Option("--candidates", help="Candidate docs to rerank")] = None,
        match_threshold: Annotated[
            float | None,
            typer.Option("--match-threshold", help="Minimum chunk similarity for document-level matching"),
        ] = None,
    ) -> None:
        _handle_stage_result(cmd)(
            target=target,
            index=index,
            top=top,
            per_chunk=per_chunk,
            candidates=candidates,
            match_threshold=match_threshold,
        )

    return app
