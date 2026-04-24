"""MCP Typer app factory."""

import typer

from wks.api.mcp.cmd_install import cmd_install
from wks.api.mcp.cmd_list import cmd_list
from wks.api.mcp.cmd_uninstall import cmd_uninstall
from wks.cli._app_factory import build_typer_app, require_subcommand
from wks.cli._handle_stage_result import _handle_stage_result
from wks.mcp.client import proxy_stdio_to_socket
from wks.mcp.paths import mcp_socket_path


def _proxy_app() -> typer.Typer:
    """Create the proxy sub-app (wksc mcp proxy ...)."""
    proxy = build_typer_app(name="proxy", help_text="SSE proxy for container access")
    require_subcommand(proxy)

    @proxy.command(name="start")
    def proxy_start(
        port: int = typer.Option(8765, "--port", help="Port to listen on"),
        host: str = typer.Option("localhost", "--host", help="Host to bind to"),
        blocking: bool = typer.Option(False, "--blocking", help="Run in foreground"),
    ) -> None:
        """Start the SSE proxy."""
        from wks.mcp.sse_proxy import run_server, start_background

        if blocking:
            run_server(host=host, port=port)
        else:
            result = start_background(host=host, port=port)
            typer.echo(result["message"])
            raise typer.Exit(0 if result["running"] else 1)

    @proxy.command(name="stop")
    def proxy_stop() -> None:
        """Stop the SSE proxy."""
        from wks.mcp.sse_proxy import stop_background

        result = stop_background()
        typer.echo(result["message"])

    @proxy.command(name="status")
    def proxy_status() -> None:
        """Check SSE proxy status."""
        from wks.mcp.sse_proxy import get_status

        result = get_status()
        if result["running"]:
            typer.echo(f"Running (pid {result['pid']})")
        else:
            typer.echo("Not running")

    return proxy


def mcp() -> typer.Typer:
    """Create and configure the MCP Typer app."""
    app = build_typer_app(name="mcp", help_text="MCP server guidance and runtime commands")
    require_subcommand(app)

    app.add_typer(_proxy_app(), name="proxy")

    @app.command(name="list")
    def list_cmd() -> None:
        """List supported MCP client targets and native commands."""
        _handle_stage_result(cmd_list)()

    @app.command(name="install")
    def install_cmd(
        name: str | None = typer.Argument(None, help="Target name"),
    ) -> None:
        """Show the native client command to install WKS MCP."""
        if name is None:
            _handle_stage_result(cmd_list)()
            return
        _handle_stage_result(cmd_install)(name)

    @app.command(name="uninstall")
    def uninstall_cmd(
        name: str | None = typer.Argument(None, help="Target name"),
    ) -> None:
        """Show the native client command to uninstall WKS MCP."""
        if name is None:
            _handle_stage_result(cmd_list)()
            return
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
