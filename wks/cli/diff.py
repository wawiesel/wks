"""Diff Typer app factory."""

from __future__ import annotations

from typing import Annotated, Any

import typer

from wks.api.diff.cmd_diff import cmd_diff
from wks.cli._handle_stage_result import _handle_stage_result


def diff() -> typer.Typer:
    """Create and configure the diff Typer app."""
    app = typer.Typer(
        name="diff",
        help="Diff operations",
        pretty_exceptions_show_locals=False,
        pretty_exceptions_enable=False,
        context_settings={"help_option_names": ["-h", "--help"], "allow_interspersed_args": True},
        invoke_without_command=True,
    )

    @app.callback(invoke_without_command=True)
    def callback(
        ctx: typer.Context,
        target_a: Annotated[str | None, typer.Argument(help="First target path or checksum")] = None,
        target_b: Annotated[str | None, typer.Argument(help="Second target path or checksum")] = None,
        engine: Annotated[
            str,
            typer.Option("--engine", "-e", help="Engine: bsdiff3, myers, sexp, semantic, or auto"),
        ] = "auto",
        context_lines: Annotated[int, typer.Option("--context-lines", help="Unified diff context lines")] = 3,
        ignore_whitespace: Annotated[
            bool, typer.Option("--ignore-whitespace", help="Ignore whitespace differences")
        ] = False,
        language: Annotated[str | None, typer.Option("--language", help="Language for AST diff")] = None,
        ignore_comments: Annotated[bool, typer.Option("--ignore-comments", help="Ignore comments in AST diff")] = True,
        semantic_modified_threshold: Annotated[
            float, typer.Option("--semantic-modified-threshold", help="Semantic modified threshold in [0,1]")
        ] = 0.75,
        semantic_unchanged_threshold: Annotated[
            float, typer.Option("--semantic-unchanged-threshold", help="Semantic unchanged threshold in [0,1]")
        ] = 0.92,
        semantic_text_model: Annotated[
            str, typer.Option("--semantic-text-model", help="Sentence-transformers model for text")
        ] = "sentence-transformers/all-MiniLM-L6-v2",
        semantic_image_model: Annotated[
            str, typer.Option("--semantic-image-model", help="CLIP model for image similarity")
        ] = "openai/clip-vit-base-patch32",
        semantic_pixel_threshold: Annotated[
            int, typer.Option("--semantic-pixel-threshold", help="Pixel threshold (0-255) for change ratio")
        ] = 10,
        semantic_max_examples: Annotated[
            int, typer.Option("--semantic-max-examples", help="Max semantic examples to include")
        ] = 8,
        timeout_seconds: Annotated[int, typer.Option("--timeout-seconds", help="Timeout in seconds")] = 60,
        max_size_mb: Annotated[int, typer.Option("--max-size-mb", help="Max size in MB")] = 100,
    ) -> None:
        """Compute a diff between two targets."""
        if ctx.invoked_subcommand is None and (target_a is None or target_b is None):
            if target_a is not None and target_b is None:
                typer.echo("Error: diff requires two targets. Usage: wksc diff <target_a> <target_b>", err=True)
            else:
                typer.echo(ctx.get_help(), err=True)
            raise typer.Exit(2)

        assert target_a is not None
        assert target_b is not None

        engine_config: dict[str, Any] = {"engine": engine}
        if engine == "myers":
            engine_config.update({"context_lines": context_lines, "ignore_whitespace": ignore_whitespace})
        elif engine == "ast":
            engine_config.update({"language": language, "ignore_comments": ignore_comments})
        elif engine == "semantic":
            engine_config.update(
                {
                    "modified_threshold": semantic_modified_threshold,
                    "unchanged_threshold": semantic_unchanged_threshold,
                    "text_model": semantic_text_model,
                    "image_model": semantic_image_model,
                    "pixel_threshold": semantic_pixel_threshold,
                    "max_examples": semantic_max_examples,
                }
            )

        config = {
            "engine_config": engine_config,
            "timeout_seconds": timeout_seconds,
            "max_size_mb": max_size_mb,
        }

        _handle_stage_result(cmd_diff)(config, target_a, target_b)

    return app
