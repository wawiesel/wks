"""Index Typer app factory."""

import typer

from wks.api.index.cmd import cmd
from wks.api.index.cmd_status import cmd_status
from wks.cli._handle_stage_result import _handle_stage_result


def index() -> typer.Typer:
    """Create and configure the index Typer app."""
    app = typer.Typer(
        name="index",
        help="Add documents to a named index",
        pretty_exceptions_show_locals=False,
        pretty_exceptions_enable=False,
        context_settings={"help_option_names": ["-h", "--help"]},
        invoke_without_command=True,
    )

    @app.callback(invoke_without_command=True)
    def callback(ctx: typer.Context) -> None:
        if ctx.invoked_subcommand is None:
            typer.echo(ctx.get_help(), err=False)
            raise typer.Exit(2)

    @app.command(name="add")
    def add_cmd(
        name: str = typer.Argument(..., help="Index name"),
        uri: str = typer.Argument(..., help="URI or file path to index"),
    ) -> None:
        """Add a document to a named index."""
        _handle_stage_result(cmd)(name, uri)

    @app.command(name="status")
    def status_cmd(
        name: str = typer.Argument("", help="Index name (all indexes if omitted)"),
    ) -> None:
        """Show index statistics."""
        _handle_stage_result(cmd_status)(name)

    return app
