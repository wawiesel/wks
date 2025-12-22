"""Typer CLI app for link."""

import typer

from wks.api.link.cmd_check import cmd_check
from wks.api.link.cmd_show import cmd_show
from wks.api.link.cmd_status import cmd_status
from wks.api.link.cmd_sync import cmd_sync
from wks.cli._handle_stage_result import handle_stage_result

app = typer.Typer(
    name="link",
    help="Manage resource edges (link)",
    pretty_exceptions_show_locals=False,
    pretty_exceptions_enable=False,
    context_settings={"help_option_names": ["-h", "--help"]},
    invoke_without_command=True,
)


@app.callback(invoke_without_command=True)
def _link_callback(ctx: typer.Context) -> None:
    """Link operations - shows available commands."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help(), err=True)
        raise typer.Exit()


@app.command(name="status")
def _status():
    """Get health and statistics for the links collection."""
    handle_stage_result(cmd_status)()


@app.command(name="show")
def _show(
    ctx: typer.Context,
    uri: str = typer.Argument(None, help="Search for edges connected to this URI"),
    direction: str = typer.Option("from", help="Direction of edges: to, from, or both"),
):
    """Show edges connected to a specific URI."""
    if not uri:
        typer.echo(ctx.get_help(), err=True)
        raise typer.Exit()
    handle_stage_result(cmd_show)(uri=uri, direction=direction)


@app.command(name="check")
def _check(
    ctx: typer.Context,
    path: str = typer.Argument(None, help="Path to file check"),
    parser: str | None = typer.Option(None, help="Parser to use (e.g., 'vault')"),
):
    """Check links in a file and verify monitoring status."""
    if not path:
        typer.echo(ctx.get_help(), err=True)
        raise typer.Exit()
    handle_stage_result(cmd_check)(path=path, parser=parser)


@app.command(name="sync")
def _sync(
    ctx: typer.Context,
    path: str = typer.Argument(None, help="Path to file or directory to sync"),
    parser: str | None = typer.Option(None, help="Parser to use (e.g., 'vault')"),
    recursive: bool = typer.Option(False, "--recursive", "-r", help="Recursively sync directory"),
    remote: bool = typer.Option(False, help="Sync and validate remote targets"),
):
    """Sync links from file/directory to database if monitored."""
    if not path:
        typer.echo(ctx.get_help(), err=True)
        raise typer.Exit()
    handle_stage_result(cmd_sync)(path=path, parser=parser, recursive=recursive, remote=remote)
