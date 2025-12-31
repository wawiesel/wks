"""Link Typer app factory."""

import typer

from wks.api.link.cmd_check import cmd_check
from wks.api.link.cmd_show import cmd_show
from wks.api.link.cmd_status import cmd_status
from wks.api.link.cmd_sync import cmd_sync
from wks.cli._handle_stage_result import _handle_stage_result


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
        uri: str = typer.Argument(..., help="URI to search for connected edges"),
        direction: str = typer.Option("from", help="Direction: to, from, or both"),
    ) -> None:
        """Show edges connected to a specific URI."""
        _handle_stage_result(cmd_show)(uri=uri, direction=direction)

    @app.command(name="check")
    def check_cmd(
        path: str = typer.Argument(..., help="Path to file to check"),
        parser: str | None = typer.Option(None, help="Parser to use (e.g., 'vault')"),
    ) -> None:
        """Check links in a file and verify monitoring status."""
        _handle_stage_result(cmd_check)(path=path, parser=parser)

    @app.command(name="sync")
    def sync_cmd(
        path: str = typer.Argument(..., help="Path to file or directory to sync"),
        parser: str | None = typer.Option(None, help="Parser to use (e.g., 'vault')"),
        recursive: bool = typer.Option(False, "--recursive", "-r", help="Recursively sync directory"),
        remote: bool = typer.Option(False, help="Sync and validate remote targets"),
    ) -> None:
        """Sync links from file/directory to database if monitored."""
        _handle_stage_result(cmd_sync)(path=path, parser=parser, recursive=recursive, remote=remote)

    return app
