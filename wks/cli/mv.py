"""Mv Typer app factory - move files within monitored paths."""

from typing import Annotated

import typer

from wks.api.mv.cmd import cmd
from wks.cli._handle_stage_result import _handle_stage_result
from wks.cli._resolve_uri_arg import _resolve_uri_arg


def mv() -> typer.Typer:
    """Create and configure the mv Typer app."""
    app = typer.Typer(
        name="mv",
        help="Move files within monitored paths",
        pretty_exceptions_show_locals=False,
        pretty_exceptions_enable=False,
        context_settings={"help_option_names": ["-h", "--help"], "allow_interspersed_args": True},
        invoke_without_command=True,
    )

    @app.callback(invoke_without_command=True)
    def callback(
        ctx: typer.Context,
        source: Annotated[str | None, typer.Argument(help="Source file path")] = None,
        dest: Annotated[str | None, typer.Argument(help="Destination file path")] = None,
    ) -> None:
        """Move a file within monitored paths.

        Both source and destination must be within monitored directories.
        The monitor database is automatically updated after the move.

        Destination filename must follow date-title format:
        - YYYY-Title_Here
        - YYYY_MM-Title_Here
        - YYYY_MM_DD-Title_Here
        """
        if source is None or dest is None:
            typer.echo(ctx.get_help(), err=True)
            raise typer.Exit(2)

        source_uri = _resolve_uri_arg(source)
        dest_uri = _resolve_uri_arg(dest)
        _handle_stage_result(cmd)(source_uri, dest_uri)

    return app
