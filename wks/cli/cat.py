"""Cat Typer app factory - print file or cached content to stdout."""

from typing import Annotated

import typer


def cat() -> typer.Typer:
    """Create and configure the cat Typer app."""
    app = typer.Typer(
        name="cat",
        help="Print content to stdout (file path or checksum)",
        pretty_exceptions_show_locals=False,
        pretty_exceptions_enable=False,
        context_settings={"help_option_names": ["-h", "--help"]},
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

        from ._run_cat import _run_cat

        _run_cat(target, engine)

    return app
