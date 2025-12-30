"""CLI implementation for cat command."""

import typer

from wks.api.cat.cmd import cmd


def _run_cat(target: str, engine_override: str | None) -> None:
    """Execute cat command and print result to stdout."""
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
