"""CLI - direct API integration.

All commands are handled by domain-specific Typer apps in wks/api/{domain}/app.py.
Each domain app implements the unified 4-stage pattern for both CLI and MCP.
"""

import subprocess
import sys
from pathlib import Path

import click
import typer

from wks.api.config.app import config_app
from wks.api.db.app import db_app
from wks.api.monitor.app import monitor_app

# TODO: Create wks/api/diff/app.py
# from wks.api.diff.app import diff_app
# from wks.api.service.app import service_app
# from wks.api.transform.app import transform_app
# from wks.api.vault.app import vault_app
from wks.display.context import get_display
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
# app.add_typer(service_app, name="service")
app.add_typer(config_app, name="config")
app.add_typer(db_app, name="db")


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    display: str = typer.Option("yaml", "--display", "-d", help="Output format: 'json' or 'yaml' (default: yaml)"),
) -> None:
    """Main CLI callback - shows help when no command is provided."""
    # Store display format in context for use by commands
    # Use ensure_object to initialize meta dict
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
        from wks.mcp.setup import install_mcp_configs

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


def _extract_live_flag(argv: list[str]) -> float | None:
    """Extract --live flag value and remove it from argv. Returns interval or None."""
    for i, arg in enumerate(argv):
        if arg.startswith("--live="):
            try:
                interval = float(arg.split("=")[1])
                argv.pop(i)
                return interval
            except (ValueError, IndexError):
                return None
        elif arg == "--live" and i + 1 < len(argv):
            try:
                interval = float(argv[i + 1])
                argv.pop(i + 1)
                argv.pop(i)
                return interval
            except (ValueError, IndexError):
                return None
    return None


def _run_live_mode(argv: list[str], interval: float) -> int:
    """Run command continuously every N seconds with live updates (CLI-only feature)."""
    import signal
    import time
    import subprocess
    from rich.live import Live
    from rich.console import Console
    from rich.text import Text
    from rich.syntax import Syntax

    # Track if we should exit
    should_exit = False

    def signal_handler(sig, frame):
        nonlocal should_exit
        should_exit = True

    # Handle Ctrl+C gracefully
    signal.signal(signal.SIGINT, signal_handler)

    console = Console()

    # Determine display format from argv for syntax highlighting
    display_format = "yaml"
    for arg in argv:
        if arg.startswith("--display="):
            display_format = arg.split("=")[1]
            break
        elif arg == "--display":
            idx = argv.index(arg)
            if idx + 1 < len(argv):
                display_format = argv[idx + 1]
            break

    # Get command path
    command_path = Path(__file__).parent.parent / "__main__.py"
    if not command_path.exists():
        # Fallback to python -m wks.cli
        command_args = ["python", "-m", "wks.cli"] + argv
    else:
        command_args = [sys.executable, str(command_path)] + argv

    def _get_command_output() -> tuple[str, str]:
        """Run command and capture stdout/stderr."""
        try:
            result = subprocess.run(
                command_args,
                capture_output=True,
                text=True,
                timeout=30,  # Prevent hanging
            )
            return result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return "", "Error: Command timed out"
        except Exception as e:
            return "", f"Error: {e}"

    def _format_output(output_text: str, fmt: str):
        """Format output with syntax highlighting."""
        if not output_text.strip():
            return Text("(no output)")
        return Syntax(output_text, fmt, theme="monokai", line_numbers=False)

    try:
        # Initial run
        stdout_content, stderr_content = _get_command_output()

        from rich.console import Group
        status_text = Text.from_ansi(stderr_content) if stderr_content else Text()
        output_syntax = _format_output(stdout_content, display_format)
        footer_text = Text("Live mode (CNTL-C to end)", style="dim")
        output_group = Group(status_text, output_syntax, footer_text)

        # Start live display
        with Live(output_group, console=console, refresh_per_second=10, screen=True) as live:
            while not should_exit:
                # Get fresh output
                stdout_content, stderr_content = _get_command_output()

                # Update display
                status_text = Text.from_ansi(stderr_content) if stderr_content else Text()
                output_syntax = _format_output(stdout_content, display_format)
                footer_text = Text("Live mode (CNTL-C to end)", style="dim")
                output_group = Group(status_text, output_syntax, footer_text)
                live.update(output_group)

                # Wait for interval (with checks for exit)
                start_time = time.time()
                while time.time() - start_time < interval and not should_exit:
                    time.sleep(0.1)

    except KeyboardInterrupt:
        pass
    finally:
        console.print("\n[dim]Live mode stopped[/dim]")

    return 0


def _run_single_command(argv: list[str]) -> int:
    """Run a single command execution and return exit code."""
    try:
        app(argv)
        return 0
    except typer.Exit as e:
        return e.exit_code
    except click.exceptions.UsageError:
        return 1
    except Exception:
        return 1


def main(argv: list[str] | None = None) -> int:
    """Main CLI entry point."""
    if argv is None:
        argv = sys.argv[1:]

    if "--version" in argv or "-v" in argv:
        return _handle_version_flag()

    # Extract and handle live mode (CLI-only feature)
    live_interval = _extract_live_flag(argv)

    if live_interval is not None and live_interval > 0:
        return _run_live_mode(argv, live_interval)

    # Handle display flag
    if argv:
        _handle_display_flag(argv)

    # Normal single execution
    return _run_single_command(argv)
