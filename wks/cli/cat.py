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

        _cat_target(target, engine)

    return app


def _cat_target(target: str, engine_override: str | None) -> None:
    """Cat content to stdout - handles both file paths and checksums."""
    from wks.api.cat.cmd import cmd

    try:
        res = cmd(target, engine=engine_override)
        # Consume progress generator
        list(res.progress_callback(res))

        if res.success:
            if isinstance(res.output, dict) and "content" in res.output:
                typer.echo(res.output["content"])
            else:
                typer.echo(f"Error: No content returned for {target}", err=True)
                raise typer.Exit(1)
        else:
            typer.echo(f"Error: {res.result}", err=True)
            raise typer.Exit(1)

    except typer.Exit:
        raise
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from None
