"""CLI - direct API integration.

All commands are handled by domain-specific Typer apps in wks/api/{domain}/app.py.
Each domain app implements the unified 4-stage pattern for both CLI and MCP.
"""

import subprocess
import sys
from pathlib import Path

import typer

from ..api.config.app import config_app
from ..api.db.app import db_app
from ..api.diff.app import diff_app
from ..api.monitor.app import monitor_app
from ..api.service.app import service_app
from ..api.transform.app import transform_app
from ..api.vault.app import vault_app
from ..display.context import get_display
from ..mcp_client import proxy_stdio_to_socket
from ..mcp_paths import mcp_socket_path
from ..utils import get_package_version

app = typer.Typer(
    pretty_exceptions_show_locals=False,
    pretty_exceptions_enable=False,
    help="WKS CLI",
    context_settings={"help_option_names": ["-h", "--help"]},
)

# Register all domain apps
app.add_typer(monitor_app, name="monitor")
app.add_typer(vault_app, name="vault")
app.add_typer(transform_app, name="transform")
app.add_typer(diff_app, name="diff")
app.add_typer(service_app, name="service")
app.add_typer(config_app, name="config")
app.add_typer(db_app, name="db")


@app.command(name="mcp", help="MCP server operations")
def mcp_command(
    command: str = typer.Argument("run", help="MCP command ('run' or 'install')", metavar="COMMAND"),
    direct: bool = typer.Option(False, "--direct", help="Run MCP directly (no socket)"),
    command_path: str | None = None,
    client: list[str] | None = None,
):
    """MCP server infrastructure command."""
    if command == "install":
        from ..mcp_setup import install_mcp_configs

        for r in install_mcp_configs(clients=client, command_override=command_path):
            print(f"[{r.client}] {r.status.upper()}: {r.message or ''}")
        sys.exit(0)

    if command == "run":
        if not direct and proxy_stdio_to_socket(mcp_socket_path()):
            sys.exit(0)
        from ..mcp_server import main as mcp_main

        mcp_main()
        sys.exit(0)

    print(f"Unknown MCP command: {command}", file=sys.stderr)
    sys.exit(2)


def _handle_version_flag() -> int:
    """Handle --version flag."""
    v = get_package_version()
    try:
        sha = (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                stderr=subprocess.DEVNULL,
                cwd=str(Path(__file__).resolve().parents[2]),
            )
            .decode()
            .strip()
        )
        v = f"{v} ({sha})"
    except Exception:
        pass
    print(f"wksc {v}")
    return 0


def _handle_display_flag(argv: list[str]) -> int:
    """Handle --display flag and remove it from argv."""
    for i, arg in enumerate(argv):
        if arg.startswith("--display="):
            display_val = arg.split("=")[1]
            if display_val in ("cli", "mcp"):
                get_display(display_val)  # type: ignore[arg-type]
            argv.pop(i)
            return 0
        elif arg == "--display" and i + 1 < len(argv):
            display_val = argv[i + 1]
            if display_val in ("cli", "mcp"):
                get_display(display_val)  # type: ignore[arg-type]
            argv.pop(i + 1)
            argv.pop(i)
            return 0
    return 0


def main(argv: list[str] | None = None) -> int:
    """Main CLI entry point."""
    if argv and ("--version" in argv or "-v" in argv):
        return _handle_version_flag()

    if argv:
        _handle_display_flag(argv)

    try:
        app(argv)
    except typer.Exit as e:
        return e.exit_code
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0
