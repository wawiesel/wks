"""CLI - thin wrapper on MCP tools.

Per CONTRIBUTING.md: CLI → MCP → API (CLI never calls API directly)
"""

import subprocess
import sys
from pathlib import Path
from typing import Any

import typer

from ..display.context import get_display
from ..mcp_client import proxy_stdio_to_socket
from ..mcp_paths import mcp_socket_path
from ..utils import expand_path, get_package_version

# =============================================================================
# Typer Apps
# =============================================================================

app = typer.Typer(
    pretty_exceptions_show_locals=False,
    pretty_exceptions_enable=False,
    help="WKS CLI",
    context_settings={"help_option_names": ["-h", "--help"]},
)
monitor_app = typer.Typer(
    name="monitor",
    help="Monitor operations",
    pretty_exceptions_show_locals=False,
    pretty_exceptions_enable=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)
app.add_typer(monitor_app, name="monitor")


# =============================================================================
# Common Helpers
# =============================================================================


def _call(tool: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
    """Call MCP tool."""
    from ..mcp_server import call_tool

    return call_tool(tool, args or {})


# Global variable for display object
display_obj_global = None


def _out(data: Any) -> None:
    """Output result."""
    global display_obj_global
    if display_obj_global is None:
        display_obj_global = get_display("cli")  # Default to cli if not set

    if isinstance(data, dict):
        display_obj_global.json_output(data)
    else:
        print(data)


def _err(result: dict) -> int:
    """Print errors, return exit code."""
    for msg in result.get("messages", []):
        print(f"{msg.get('type', 'error')}: {msg.get('text', '')}", file=sys.stderr)
    return 0 if result.get("success", True) else 1


# =============================================================================
# Commands: config, transform, cat, diff
# =============================================================================


@app.command(name="config", help="Show config")
def config_command():
    r = _call("wksm_config")
    _out(r.get("data", r))
    sys.exit(_err(r))


@app.command(name="transform", help="Transform file")
def transform_command(
    engine: str = typer.Argument(..., help="Transformation engine"),
    file_path: str = typer.Argument(..., help="Path to the file to transform"),
    output: str | None = typer.Option(None, "-o", "--output", help="Output file path"),
):
    path = expand_path(file_path)
    if not path.exists():
        print(f"Error: File not found: {path}", file=sys.stderr)
        sys.exit(2)
    r = _call("wksm_transform", {"file_path": str(path), "engine": engine, "options": {}})
    if r.get("success"):
        print(r.get("data", {}).get("checksum", ""))
    sys.exit(_err(r))


@app.command(name="cat", help="Display content")
def cat_command(
    input_path: str = typer.Argument(..., help="Input file path"),
    output_path: str | None = typer.Option(None, "-o", "--output", help="Output file path"),
):
    r = _call("wksm_cat", {"target": input_path})
    if r.get("success"):
        content = r.get("data", {}).get("content", "")
        if output_path:
            Path(output_path).write_text(content)
            print(f"Saved to {output_path}", file=sys.stderr)
        else:
            print(content)
    sys.exit(_err(r))


@app.command(name="diff", help="Compare files")
def diff_command(
    engine: str = typer.Argument(..., help="Diff engine"),
    file1: str = typer.Argument(..., help="Path to the first file"),
    file2: str = typer.Argument(..., help="Path to the second file"),
):
    r = _call("wksm_diff", {"engine": engine, "target_a": file1, "target_b": file2})
    if r.get("success"):
        print(r.get("data", {}).get("diff", ""))
    sys.exit(_err(r))


# =============================================================================
# Monitor commands
# =============================================================================


@monitor_app.command(name="status", help="Show monitor status")
def monitor_status_command():
    _out(_call("wksm_monitor_status"))


@monitor_app.command(name="check", help="Check monitor path")
def monitor_check_command(
    path: str = typer.Argument(..., help="Path to check"),
):
    _out(_call("wksm_monitor_check", {"path": path}))


@monitor_app.command(name="validate", help="Validate monitor configuration")
def monitor_validate_command():
    r = _call("wksm_monitor_validate")
    _out(r)
    if r.get("issues"):
        sys.exit(1)


# =============================================================================
# Monitor list commands (include_paths, exclude_paths, etc.)
# =============================================================================

lists = [
    "include_paths",
    "exclude_paths",
    "include_dirnames",
    "exclude_dirnames",
    "include_globs",
    "exclude_globs",
]


def create_list_commands(list_name: str):
    list_app = typer.Typer(
        name=list_name.replace("_", "-"),
        help=f"Manage {list_name.replace('_', ' ')}",
        pretty_exceptions_show_locals=False,
        pretty_exceptions_enable=False,
        context_settings={"help_option_names": ["-h", "--help"]},
    )
    monitor_app.add_typer(list_app)

    @list_app.command(name="list", help=f"List {list_name.replace('_', ' ')}")
    def _list_cmd():
        _out(_call("wksm_monitor_list", {"list_name": list_name}))

    @list_app.command(name="add", help=f"Add to {list_name.replace('_', ' ')}")
    def _add_cmd(value: str = typer.Argument(..., help="Value to add")):
        r = _call("wksm_monitor_add", {"list_name": list_name, "value": value})
        print(f"{'Added' if r.get('success') else 'Failed'}: {value}", file=sys.stderr)
        sys.exit(0 if r.get("success") else 1)

    @list_app.command(name="remove", help=f"Remove from {list_name.replace('_', ' ')}")
    def _remove_cmd(value: str = typer.Argument(..., help="Value to remove")):
        r = _call("wksm_monitor_remove", {"list_name": list_name, "value": value})
        print(f"{'Removed' if r.get('success') else 'Failed'}: {value}", file=sys.stderr)
        sys.exit(0 if r.get("success") else 1)


for list_name in lists:
    create_list_commands(list_name)

# =============================================================================
# Monitor managed commands
# =============================================================================


@monitor_app.command(name="managed-list", help="List managed paths")
def monitor_managed_list_command():
    _out(_call("wksm_monitor_managed_list", {}))


@monitor_app.command(name="managed-add", help="Add a managed path")
def monitor_managed_add_command(
    path: str = typer.Argument(..., help="Path to manage"),
    priority: int = typer.Argument(..., help="Priority of the path"),
):
    r = _call("wksm_monitor_managed_add", {"path": path, "priority": priority})
    print(f"{'Added' if r.get('success') else 'Failed'}", file=sys.stderr)
    sys.exit(0 if r.get("success") else 1)


@monitor_app.command(name="managed-remove", help="Remove a managed path")
def monitor_managed_remove_command(
    path: str = typer.Argument(..., help="Path to unmanage"),
):
    r = _call("wksm_monitor_managed_remove", {"path": path})
    print(f"{'Removed' if r.get('success') else 'Failed'}", file=sys.stderr)
    sys.exit(0 if r.get("success") else 1)


@monitor_app.command(name="managed-set-priority", help="Set priority of a managed path")
def monitor_managed_set_priority_command(
    path: str = typer.Argument(..., help="Path to set priority for"),
    priority: int = typer.Argument(..., help="New priority of the path"),
):
    r = _call("wksm_monitor_managed_set_priority", {"path": path, "priority": priority})
    print(f"{'Updated' if r.get('success') else 'Failed'}", file=sys.stderr)
    sys.exit(0 if r.get("success") else 1)


# =============================================================================
# Vault commands
# =============================================================================


@app.command(name="vault-status", help="Show vault status")
def vault_status_command():
    _out(_call("wksm_vault_status", {}))
    sys.exit(0)


@app.command(name="vault-sync", help="Sync vault")
def vault_sync_command(
    batch_size: int = typer.Option(1000, "--batch-size", help="Batch size for sync"),
):
    r = _call("wksm_vault_sync", {"batch_size": batch_size})
    _out(r)
    sys.exit(0)


@app.command(name="vault-validate", help="Validate vault configuration")
def vault_validate_command():
    _out(_call("wksm_vault_validate", {}))
    sys.exit(0)


@app.command(name="vault-fix-symlinks", help="Fix vault symlinks")
def vault_fix_symlinks_command():
    _out(_call("wksm_vault_fix_symlinks", {}))
    sys.exit(0)


@app.command(name="vault-links", help="Show vault links")
def vault_links_command(
    file_path: str = typer.Argument(..., help="Path to the file"),
    direction: str = typer.Option(
        "both", "--direction", help="Direction of links", rich_help_panel="Vault Options"
    ),
):
    r = _call(
        "wksm_vault_links",
        {"file_path": file_path, "direction": direction},
    )
    _out(r)
    sys.exit(0)


# =============================================================================
# DB commands
# =============================================================================


@app.command(name="db-monitor", help="Query monitor database via MCP")
def db_monitor_command():
    r = _call("wksm_db_monitor", {})
    _out(r)
    sys.exit(_err(r))


@app.command(name="db-vault", help="Query vault database via MCP")
def db_vault_command():
    r = _call("wksm_db_vault", {})
    _out(r)
    sys.exit(_err(r))


@app.command(name="db-transform", help="Query transform database via MCP")
def db_transform_command():
    r = _call("wksm_db_transform", {})
    _out(r)
    sys.exit(_err(r))


# =============================================================================
# Service commands
# =============================================================================


@app.command(name="service-status", help="Show daemon/service status via MCP")
def service_status_command():
    r = _call("wksm_service", {})
    _out(r.get("data", r))
    sys.exit(_err(r))


# =============================================================================
# MCP server commands
# =============================================================================


@app.command(name="mcp", help="MCP server operations")
def mcp_command(
    command: str = typer.Argument(
        "run",
        help="MCP command to execute ('run' or 'install')",
        metavar="COMMAND",
    ),
    direct: bool = typer.Option(False, "--direct", help="Run MCP directly (no socket)"),
    command_path: str | None = typer.Option(None, help="Command path for install"),
    client: list[str] | None = typer.Option(
        None, "--client", help="Client for install", rich_help_panel="MCP Options"
    ),
):
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

    # Unknown command
    print(f"Unknown MCP command: {command}", file=sys.stderr)
    sys.exit(2)


# =============================================================================
# Main entry point
# =============================================================================


def main(argv: list[str] | None = None) -> int:
    """Main CLI entry point."""
    global display_obj_global

    # Handle --version separately as Typer's built-in --version is harder to customize
    if argv and ("--version" in argv or "-v" in argv):
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

    # Handle --display separately
    display_arg_index = -1
    for i, arg in enumerate(argv or []):
        if arg.startswith("--display="):
            display_obj_global = get_display(arg.split("=")[1])
            display_arg_index = i
            break
        elif arg == "--display" and i + 1 < len(argv or []):
            display_obj_global = get_display(argv[i + 1])
            display_arg_index = i
            # Also remove the next argument which is the display value
            break
    if display_arg_index != -1:
        # Remove --display argument and its value from argv
        if argv[display_arg_index].startswith("--display="):
            argv.pop(display_arg_index)
        else:
            argv.pop(display_arg_index + 1)
            argv.pop(display_arg_index)

    try:
        app(argv)
    except typer.Exit as e:
        return e.exit_code
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0
