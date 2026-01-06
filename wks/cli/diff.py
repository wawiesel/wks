"""Diff Typer app factory."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import asdict
from typing import Annotated, Any

import typer

from wks.api.config.StageResult import StageResult
from wks.api.diff.DiffMetadata import DiffMetadata
from wks.api.diff.DiffResult import DiffResult
from wks.cli._handle_stage_result import _handle_stage_result
from wks.mcp.call_tool import call_tool


def diff() -> typer.Typer:
    """Create and configure the diff Typer app."""
    app = typer.Typer(
        name="diff",
        help="Diff operations",
        pretty_exceptions_show_locals=False,
        pretty_exceptions_enable=False,
        context_settings={"help_option_names": ["-h", "--help"]},
        invoke_without_command=True,
    )

    @app.callback(invoke_without_command=True)
    def callback(
        ctx: typer.Context,
        target_a: Annotated[str | None, typer.Argument(help="First target path or checksum")] = None,
        target_b: Annotated[str | None, typer.Argument(help="Second target path or checksum")] = None,
        engine: Annotated[str | None, typer.Option("--engine", "-e", help="Engine: bsdiff4, myers, ast")] = None,
        context_lines: Annotated[int, typer.Option("--context-lines", help="Unified diff context lines")] = 3,
        ignore_whitespace: Annotated[
            bool, typer.Option("--ignore-whitespace", help="Ignore whitespace differences")
        ] = False,
        language: Annotated[str | None, typer.Option("--language", help="Language for AST diff")] = None,
        ignore_comments: Annotated[bool, typer.Option("--ignore-comments", help="Ignore comments in AST diff")] = True,
        timeout_seconds: Annotated[int, typer.Option("--timeout-seconds", help="Timeout in seconds")] = 60,
        max_size_mb: Annotated[int, typer.Option("--max-size-mb", help="Max size in MB")] = 100,
    ) -> None:
        """Compute a diff between two targets via MCP."""
        if ctx.invoked_subcommand is None and (target_a is None or target_b is None or engine is None):
            typer.echo(ctx.get_help(), err=True)
            raise typer.Exit(1)

        assert target_a is not None
        assert target_b is not None

        engine_config: dict[str, Any] = {"engine": engine}
        if engine == "myers":
            engine_config.update({"context_lines": context_lines, "ignore_whitespace": ignore_whitespace})
        elif engine == "ast":
            engine_config.update({"language": language, "ignore_comments": ignore_comments})

        config = {
            "engine_config": engine_config,
            "timeout_seconds": timeout_seconds,
            "max_size_mb": max_size_mb,
        }

        def mcp_cmd(cfg: dict[str, Any], a: str, b: str) -> StageResult:
            def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
                yield (0.1, "Calling MCP tool")
                response = call_tool("wksm_diff", {"config": cfg, "target_a": a, "target_b": b})
                yield (0.8, "Processing response")

                if not response.get("success"):
                    error_message = response.get("error", "Unknown MCP error")
                    metadata = DiffMetadata(
                        engine_used=str(engine or "unknown"),
                        is_identical=False,
                        file_type_a=None,
                        file_type_b=None,
                        checksum_a=None,
                        checksum_b=None,
                        encoding_a=None,
                        encoding_b=None,
                    )
                    failure = DiffResult(
                        status="failure",
                        metadata=metadata,
                        diff_output=None,
                        message=error_message,
                        error_details={"errors": [error_message]},
                    )
                    result_obj.result = f"Diff failed: {error_message}"
                    result_obj.output = asdict(failure)
                    result_obj.success = False
                    yield (1.0, "Failed")
                    return

                data = response.get("data")
                if not isinstance(data, dict):
                    metadata = DiffMetadata(
                        engine_used=str(engine or "unknown"),
                        is_identical=False,
                        file_type_a=None,
                        file_type_b=None,
                        checksum_a=None,
                        checksum_b=None,
                        encoding_a=None,
                        encoding_b=None,
                    )
                    failure = DiffResult(
                        status="failure",
                        metadata=metadata,
                        diff_output=None,
                        message="Invalid MCP response format.",
                        error_details={"errors": ["MCP returned non-dict data."]},
                    )
                    result_obj.result = "Diff failed: invalid MCP response."
                    result_obj.output = asdict(failure)
                    result_obj.success = False
                    yield (1.0, "Failed")
                    return

                result_obj.result = "Diff completed."
                result_obj.output = data
                result_obj.success = True
                yield (1.0, "Complete")

            return StageResult(
                announce=f"Diffing {a} vs {b}...",
                progress_callback=do_work,
            )

        _handle_stage_result(mcp_cmd)(config, target_a, target_b)

    return app
