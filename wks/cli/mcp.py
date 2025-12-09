"""MCP Typer app that registers all MCP commands."""

import typer

from wks.cli.handle_stage_result import handle_stage_result
from wks.api.mcp.cmd_install import cmd_install
from wks.api.mcp.cmd_list import cmd_list
from wks.api.mcp.cmd_uninstall import cmd_uninstall

mcp_app = typer.Typer(
    name="mcp",
    help="MCP installation management",
    pretty_exceptions_show_locals=False,
    pretty_exceptions_enable=False,
    context_settings={"help_option_names": ["-h", "--help"]},
    invoke_without_command=True,
)


@mcp_app.callback(invoke_without_command=True)
def mcp_callback(ctx: typer.Context) -> None:
    """MCP operations - shows available commands."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help(), err=True)
        raise typer.Exit()


# Register commands with StageResult handler
def install_command(
    ctx: typer.Context,
    name: str | None = typer.Argument(None, help="Installation name"),
) -> None:
    """Install WKS MCP server for the named installation."""
    if name is None:
        typer.echo("Error: Installation name is required", err=True)
        typer.echo(ctx.get_help(), err=True)
        raise typer.Exit(1)
    wrapped = handle_stage_result(cmd_install)
    wrapped(name)


def uninstall_command(
    ctx: typer.Context,
    name: str | None = typer.Argument(None, help="Installation name"),
) -> None:
    """Uninstall WKS MCP server for the named installation."""
    if name is None:
        typer.echo("Error: Installation name is required", err=True)
        typer.echo(ctx.get_help(), err=True)
        raise typer.Exit(1)
    wrapped = handle_stage_result(cmd_uninstall)
    wrapped(name)


mcp_app.command(name="list")(handle_stage_result(cmd_list))
mcp_app.command(name="install")(install_command)
mcp_app.command(name="uninstall")(uninstall_command)

