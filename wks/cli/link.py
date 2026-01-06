"""Link Typer app factory."""

from typing import Annotated

import typer

from wks.api.config.URI import URI
from wks.api.link.cmd_check import cmd_check
from wks.api.link.cmd_show import Direction, cmd_show
from wks.api.link.cmd_status import cmd_status
from wks.api.link.cmd_sync import cmd_sync
from wks.cli._handle_stage_result import _handle_stage_result
from wks.cli._resolve_uri_arg import _resolve_uri_arg


def link() -> typer.Typer:
    """Create and configure the link Typer app."""
    app = typer.Typer(
        name="link",
        help="Manage resource edges (link)",
        pretty_exceptions_show_locals=False,
        pretty_exceptions_enable=False,
        context_settings={"help_option_names": ["-h", "--help"]},
        invoke_without_command=True,
    )

    @app.callback(invoke_without_command=True)
    def callback(ctx: typer.Context) -> None:
        if ctx.invoked_subcommand is None:
            typer.echo(ctx.get_help(), err=True)
            raise typer.Exit()

    @app.command(name="status")
    def status_cmd() -> None:
        """Get health and statistics for the links collection."""
        _handle_stage_result(cmd_status)()

    @app.command(name="show")
    def show_cmd(
        uri: Annotated[URI, typer.Argument(parser=_resolve_uri_arg, help="URI to search for connected edges")],
        direction: Annotated[Direction, typer.Option(help="Direction: to, from, or both")] = Direction.FROM,
    ) -> None:
        """Show edges connected to a specific URI."""
        _handle_stage_result(cmd_show)(uri=uri, direction=direction)

    @app.command(name="check")
    def check_cmd(
        path: Annotated[URI, typer.Argument(parser=_resolve_uri_arg, help="Path to file to check")],
        parser: Annotated[str | None, typer.Option(help="Parser to use (e.g., 'vault')")] = None,
    ) -> None:
        """Check links in a file and verify monitoring status."""
        _handle_stage_result(cmd_check)(uri=path, parser=parser)

    @app.command(name="sync")
    def sync_cmd(
        path: Annotated[URI, typer.Argument(parser=_resolve_uri_arg, help="Path to file or directory to sync")],
        parser: Annotated[str | None, typer.Option(help="Parser to use (e.g., 'vault')")] = None,
        recursive: Annotated[bool, typer.Option("--recursive", "-r", help="Recursively sync directory")] = False,
        remote: Annotated[bool, typer.Option(help="Sync and validate remote targets")] = False,
    ) -> None:
        """Sync links from file/directory to database if monitored."""
        _handle_stage_result(cmd_sync)(uri=path, parser=parser, recursive=recursive, remote=remote)

    return app
