"""Diff Typer app."""

from typing import Annotated

import typer

from wks.api.diff.cmd import cmd
from wks.cli._handle_stage_result import _handle_stage_result


def diff() -> typer.Typer:
    """Create diff Typer app."""
    app = typer.Typer(
        name="diff",
        help="Compute diff between targets",
        pretty_exceptions_show_locals=False,
        pretty_exceptions_enable=False,
        context_settings={"help_option_names": ["-h", "--help"]},
        invoke_without_command=True,
    )

    @app.callback(invoke_without_command=True)
    def callback(
        target1: Annotated[str, typer.Argument(help="First target (path or checksum)")],
        target2: Annotated[str, typer.Argument(help="Second target (path or checksum)")],
        engine: Annotated[str | None, typer.Option("--engine", "-e", help="Engine to use")] = None,
    ) -> None:
        """Compute diff."""

        def result_printer(output: dict) -> None:
            if "content" in output:
                typer.echo(output["content"])

        _handle_stage_result(cmd, result_printer=result_printer)(target1=target1, target2=target2, engine=engine)

    return app
