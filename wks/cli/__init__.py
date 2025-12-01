"""Main CLI entry point - thin wrapper on top of MCP tools.

CLI is a thin user interface layer that:
- Parses command-line arguments
- Calls MCP tools (source of truth for all business logic)
- Formats MCP results for human-readable output
"""

import argparse
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from ..display.context import add_display_argument, get_display
from ..mcp_client import proxy_stdio_to_socket
from ..mcp_paths import mcp_socket_path
from ..utils import expand_path, get_package_version


def _handle_mcp_result(result: dict) -> tuple[int, dict]:
    """Handle structured MCP result and display messages.

    MCP is the source of truth for all errors, warnings, and messages.
    This function displays them to stderr and returns the data.

    Returns:
        Tuple of (exit_code, data dict)
    """
    success = result.get("success", False)
    data = result.get("data", {})
    messages = result.get("messages", [])

    # Display all messages to stderr (MCP is source of truth)
    for msg in messages:
        msg_type = msg.get("type", "info")
        msg_text = msg.get("text", "")
        msg_details = msg.get("details")

        if msg_type == "error":
            print(f"Error: {msg_text}", file=sys.stderr)
            if msg_details:
                print(f"  Details: {msg_details}", file=sys.stderr)
        elif msg_type == "warning":
            print(f"Warning: {msg_text}", file=sys.stderr)
            if msg_details:
                print(f"  Details: {msg_details}", file=sys.stderr)
        elif msg_type == "status":
            print(f"{msg_text}", file=sys.stderr)
        elif msg_type == "info":
            print(f"Info: {msg_text}", file=sys.stderr)
        elif msg_type == "success":
            print(f"Success: {msg_text}", file=sys.stderr)

    exit_code = 0 if success else 2
    return exit_code, data


# Simple MCP-wrapped commands
def _cmd_transform(args: argparse.Namespace) -> int:
    """Transform file using specified engine."""
    from ..mcp_server import call_tool

    file_path = expand_path(args.file_path)
    if not file_path.exists():
        print(f"Error: File not found: {file_path}", file=sys.stderr)
        return 2

    result_dict = call_tool("wksm_transform", {
        "file_path": str(file_path),
        "engine": args.engine,
        "options": {}
    })

    exit_code, data = _handle_mcp_result(result_dict)
    if exit_code != 0:
        return exit_code

    checksum = data.get("checksum", "")
    if args.output:
        print(f"Note: --output not yet supported via MCP, cache key: {checksum}", file=sys.stderr)
    elif checksum:
        print(checksum)

    return exit_code


def _cmd_cat(args: argparse.Namespace) -> int:
    """Display or save transformed content."""
    from ..mcp_server import call_tool

    result_dict = call_tool("wksm_cat", {"target": args.input})

    exit_code, data = _handle_mcp_result(result_dict)
    if exit_code != 0:
        return exit_code

    content = data.get("content", "")
    if args.output:
        Path(args.output).write_text(content)
        print(f"Saved to {args.output}", file=sys.stderr)
    else:
        print(content)

    return exit_code


def _cmd_diff(args: argparse.Namespace) -> int:
    """Compare two files using specified diff engine."""
    from ..mcp_server import call_tool

    result_dict = call_tool("wksm_diff", {
        "engine": args.engine,
        "target_a": args.file1,
        "target_b": args.file2
    })

    exit_code, data = _handle_mcp_result(result_dict)
    if exit_code != 0:
        return exit_code

    diff_result = data.get("diff", "")
    if diff_result:
        print(diff_result)

    return exit_code


def main(argv: Optional[List[str]] = None) -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(prog="wksc", description="WKS management CLI")
    sub = parser.add_subparsers(dest="cmd")

    # Version
    pkg_version = get_package_version()
    git_sha = ""
    try:
        repo_root = Path(__file__).resolve().parents[2]
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            cwd=str(repo_root),
        )
        git_sha = out.decode("utf-8", errors="ignore").strip()
    except Exception:
        git_sha = ""
    version_str = f"wksc {pkg_version}"
    if git_sha:
        version_str = f"{version_str} ({git_sha})"
    parser.add_argument("--version", action="version", version=version_str)

    # Display mode
    add_display_argument(parser)

    # Simple MCP-wrapped commands
    transform_parser = sub.add_parser("transform", help="Transform file using specified engine")
    transform_parser.add_argument("engine", help="Transform engine name (e.g., 'docling')")
    transform_parser.add_argument("file_path", help="Path to file to transform")
    transform_parser.add_argument("-o", "--output", help="Output file path")
    transform_parser.set_defaults(func=_cmd_transform)

    cat_parser = sub.add_parser("cat", help="Display or save transformed content")
    cat_parser.add_argument("input", help="File path or cache checksum")
    cat_parser.add_argument("-o", "--output", help="Output file path")
    cat_parser.set_defaults(func=_cmd_cat)

    diff_parser = sub.add_parser("diff", help="Compare two files using diff engine")
    diff_parser.add_argument("engine", help="Diff engine name (e.g., 'bsdiff3', 'myers')")
    diff_parser.add_argument("file1", help="First file path")
    diff_parser.add_argument("file2", help="Second file path")
    diff_parser.set_defaults(func=_cmd_diff)

    # Commands with more complex logic (imported from cli_commands)
    from ..cli_commands.commands.config import show_config
    from ..cli_commands.commands.monitor import setup_monitor_parser
    from ..cli_commands.commands.service import setup_service_parser
    from ..cli_commands.commands.vault import setup_vault_parser

    cfg = sub.add_parser("config", help="Show configuration file")
    cfg.set_defaults(func=show_config)

    setup_service_parser(sub)
    setup_monitor_parser(sub)
    setup_vault_parser(sub)

    # DB command (has subcommands)
    from .commands.db import setup_db_parser
    db_parser = setup_db_parser(sub)

    # MCP server command
    mcp = sub.add_parser("mcp", help="MCP server for AI integration")
    mcpsub = mcp.add_subparsers(dest="mcp_cmd")
    mcprun = mcpsub.add_parser("run", help="Start MCP server")
    mcprun.add_argument("--direct", action="store_true", help="Run server inline")

    def mcp_run(args: argparse.Namespace) -> int:
        if not args.direct:
            socket_path = mcp_socket_path()
            if proxy_stdio_to_socket(socket_path):
                return 0
        from ..mcp_server import main as mcp_main
        mcp_main()
        return 0
    mcprun.set_defaults(func=mcp_run)

    mcpinstall = mcpsub.add_parser("install", help="Register MCP server with clients")
    mcpinstall.add_argument("--command-path", dest="command_path", help="Override executable path")
    mcpinstall.add_argument("--client", dest="clients", action="append", choices=["cursor", "claude", "gemini"])

    def mcp_install(args: argparse.Namespace) -> int:
        from ..mcp_setup import install_mcp_configs
        results = install_mcp_configs(clients=args.clients, command_override=args.command_path)
        for res in results:
            print(f"[{res.client}] {res.status.upper()}: {res.message or ''}".rstrip())
        return 0
    mcpinstall.set_defaults(func=mcp_install)

    # Parse and execute
    args = parser.parse_args(argv)
    if not hasattr(args, "display") or args.display is None:
        args.display = "cli"
    args.display_obj = get_display(args.display)

    if not hasattr(args, "func"):
        if hasattr(args, "cmd") and args.cmd == "config":
            cfg.print_help()
            return 2
        parser.print_help()
        return 2

    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130
    except Exception as e:
        if args.display_obj:
            args.display_obj.error(f"Command failed: {e}")
        else:
            print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
