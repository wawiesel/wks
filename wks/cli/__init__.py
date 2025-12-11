"""CLI - direct API integration.

All commands are handled by domain-specific Typer apps in wks/api/{domain}/app.py.
Each domain app implements the unified 4-stage pattern for both CLI and MCP.
"""

import subprocess
import sys
from pathlib import Path

import click
import typer

from wks.cli.config import config_app
from wks.cli.daemon import daemon_app
from wks.cli.database import db_app
from wks.cli.mcp import mcp_app
from wks.cli.monitor import monitor_app

# TODO: Create wks/api/diff/app.py
# from wks.api.diff.app import diff_app
# from wks.api.transform.app import transform_app
# from wks.api.vault.app import vault_app
from wks.utils.display.context import get_display
from wks.mcp.client import proxy_stdio_to_socket
from wks.mcp.paths import mcp_socket_path
from wks.utils import get_package_version

app = typer.Typer(
    pretty_exceptions_show_locals=False,
    pretty_exceptions_enable=False,
    help="WKS CLI",
    context_settings={"help_option_names": ["-h", "--help"]},
    invoke_without_command=True,
)

# Register all domain apps
app.add_typer(monitor_app, name="monitor")
# app.add_typer(vault_app, name="vault")
# app.add_typer(transform_app, name="transform")
# app.add_typer(diff_app, name="diff")
app.add_typer(daemon_app, name="daemon")
app.add_typer(config_app, name="config")
app.add_typer(db_app, name="database")
app.add_typer(mcp_app, name="mcp")


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    display: str = typer.Option("yaml", "--display", "-d", help="Output format: 'json' or 'yaml' (default: yaml)"),
) -> None:
    """Main CLI callback - shows help when no command is provided."""
    # Validate display format
    if display not in ("json", "yaml"):
        typer.echo(f"Error: --display must be 'json' or 'yaml', got '{display}'", err=True)
        raise typer.Exit(1)

    # Store display format in context for use by commands
    ctx.ensure_object(dict)
    if ctx.obj is None:
        ctx.obj = {}
    ctx.obj["display_format"] = display

    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()


@app.command(name="mcp", help="MCP server operations")
def mcp_command(
    command: str = typer.Argument("run", help="MCP command ('run' or 'install')", metavar="COMMAND"),
    direct: bool = typer.Option(False, "--direct", help="Run MCP directly (no socket)"),
    command_path: str | None = None,
    client: list[str] | None = None,
):
    """MCP server infrastructure command."""
    if command == "install":
        from wks.api.mcp.install_mcp_configs import install_mcp_configs

        for r in install_mcp_configs(clients=client, command_override=command_path):
            print(f"[{r.client}] {r.status.upper()}: {r.message or ''}")
        sys.exit(0)

    if command == "run":
        if not direct and proxy_stdio_to_socket(mcp_socket_path()):
            sys.exit(0)
        from wks.mcp.server import main as mcp_main

        mcp_main()
        sys.exit(0)

    print(f"Unknown MCP command: {command}", file=sys.stderr)
    sys.exit(2)


def _handle_version_flag() -> int:
    """Handle --version flag by calling the API command."""
    from wks.api.config.cmd_version import cmd_version
    from wks.cli._run_single_execution import _run_single_execution
    from wks.utils.display.context import get_display

    display = get_display("cli")
    result = cmd_version()
    # Execute progress callback
    list(result.progress_callback(result))
    # Display result
    if result.success:
        # Extract version from output and print in CLI format
        full_version = result.output.get("full_version", result.output.get("version", "unknown"))
        print(f"wksc {full_version}")
    else:
        print(f"wksc {result.output.get('version', 'unknown')}")
    return 0 if result.success else 1


def _run_single_command(argv: list[str]) -> int:
    """Run a single command execution and return exit code."""
    try:
        app(argv)
        return 0
    except typer.Exit as e:
        return e.exit_code
    except click.exceptions.UsageError as e:
        typer.echo(f"Usage error: {e}", err=True)
        return 1
    except Exception as e:
        typer.echo(f"Unhandled error: {e}", err=True)
        return 1


def main(argv: list[str] | None = None) -> int:
    """Main CLI entry point."""
    if argv is None:
        argv = sys.argv[1:]

    if "--version" in argv or "-v" in argv:
        return _handle_version_flag()

    # Normal single execution (--display is handled by Typer callback)
    return _run_single_command(argv)
