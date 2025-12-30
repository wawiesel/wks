"""MCP Typer app factory."""

import typer

from wks.api.mcp.cmd_install import cmd_install
from wks.api.mcp.cmd_list import cmd_list
from wks.api.mcp.cmd_uninstall import cmd_uninstall
from wks.cli._handle_stage_result import _handle_stage_result
from wks.mcp.client import proxy_stdio_to_socket
from wks.mcp.paths import mcp_socket_path


def mcp() -> typer.Typer:
    """Create and configure the MCP Typer app."""
    app = typer.Typer(
        name="mcp",
        help="MCP installation management",
        pretty_exceptions_show_locals=False,
        pretty_exceptions_enable=False,
        context_settings={"help_option_names": ["-h", "--help"]},
        invoke_without_command=True,
    )

    @app.callback(invoke_without_command=True)
    def callback(ctx: typer.Context) -> None:
        """MCP operations - shows available commands."""
        if ctx.invoked_subcommand is None:
            typer.echo(ctx.get_help(), err=True)
            raise typer.Exit()

    @app.command(name="list")
    def list_cmd() -> None:
        """List MCP installations."""
        _handle_stage_result(cmd_list)()

    @app.command(name="install")
    def install_cmd(
        name: str = typer.Argument(..., help="Installation name"),
        install_type: str = typer.Option("mcpServersJson", "--type", help="Installation type"),
        settings_path: str | None = typer.Option(None, "--settings-path", help="Path to settings file"),
    ) -> None:
        """Install WKS MCP server for the named installation."""
        _handle_stage_result(cmd_install)(name, install_type, settings_path)

    @app.command(name="uninstall")
    def uninstall_cmd(
        name: str = typer.Argument(..., help="Installation name"),
    ) -> None:
        """Uninstall WKS MCP server for the named installation."""
        _handle_stage_result(cmd_uninstall)(name)

    @app.command(name="run")
    def run_cmd(
        direct: bool = typer.Option(False, "--direct", help="Run MCP directly over stdio (no socket proxy)"),
    ) -> None:
        """Run the MCP server."""
        if not direct and proxy_stdio_to_socket(mcp_socket_path()):
            raise typer.Exit(0)
        # Inline import to avoid circular dependency
        from wks.mcp.main import main as mcp_main

        mcp_main()

    return app
