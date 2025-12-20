"""Typer CLI app for link."""

import typer

from wks.api.link.cmd_check import cmd_check
from wks.api.link.cmd_show import cmd_show
from wks.api.link.cmd_status import cmd_status
from wks.api.link.cmd_sync import cmd_sync
from wks.cli._handle_stage_result import handle_stage_result

app = typer.Typer(name="link", help="Manage resource edges (link)")


@app.command()
def status():
    """Get health and statistics for the links collection."""
    handle_stage_result(cmd_status)()


@app.command()
def show(
    uri: str = typer.Argument(..., help="Search for edges connected to this URI"),
    direction: str = typer.Option("from", help="Direction of edges: to, from, or both"),
):
    """Show edges connected to a specific URI."""
    handle_stage_result(cmd_show)(uri=uri, direction=direction)


@app.command()
def check(
    path: str = typer.Argument(..., help="Path to file check"),
    parser: str | None = typer.Option(None, help="Parser to use (e.g., 'vault')"),
):
    """Check links in a file and verify monitoring status."""
    handle_stage_result(cmd_check)(path=path, parser=parser)


@app.command()
def sync(
    path: str = typer.Argument(..., help="Path to file or directory to sync"),
    parser: str | None = typer.Option(None, help="Parser to use (e.g., 'vault')"),
    recursive: bool = typer.Option(False, "--recursive", "-r", help="Recursively sync directory"),
    remote: bool = typer.Option(False, help="Sync and validate remote targets"),
):
    """Sync links from file/directory to database if monitored."""
    handle_stage_result(cmd_sync)(path=path, parser=parser, recursive=recursive, remote=remote)
