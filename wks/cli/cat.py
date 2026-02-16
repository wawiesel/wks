"""Cat Typer app factory - print file or cached content to stdout."""

from typing import Annotated

import typer

from wks.api.cat.cmd import cmd
from wks.cli._handle_stage_result import _handle_stage_result


def cat() -> typer.Typer:
    """Create and configure the cat Typer app."""
    app = typer.Typer(
        name="cat",
        help="Print content to stdout (file path or checksum)",
        pretty_exceptions_show_locals=False,
        pretty_exceptions_enable=False,
        context_settings={"help_option_names": ["-h", "--help"], "allow_interspersed_args": True},
        invoke_without_command=True,
    )

    @app.callback(invoke_without_command=True)
    def callback(
        ctx: typer.Context,
        target: Annotated[str | None, typer.Argument(help="File path or checksum")] = None,
        engine: Annotated[str | None, typer.Option("--engine", "-e", help="Engine to use")] = None,
    ) -> None:
        """Print content to stdout.

        TARGET can be:
        - A file path: transforms file and prints content
        - A checksum (64 hex chars): prints cached content directly
        """
        if target is None:
            typer.echo(ctx.get_help(), err=True)
            raise typer.Exit()

        # result_printer allows us to print the 'content' field to stdout on success
        def result_printer(output: dict) -> None:
            if "content" in output:
                typer.echo(output["content"])

        _handle_stage_result(cmd, result_printer=result_printer)(target, engine=engine)

    return app
