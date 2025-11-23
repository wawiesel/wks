"""Main CLI entry point - sets up argument parser and routes commands."""

import argparse
import subprocess
from pathlib import Path
from typing import List, Optional

from ..display.context import add_display_argument, get_display
from ..mcp_client import proxy_stdio_to_socket
from ..mcp_paths import mcp_socket_path
from ..utils import get_package_version
from .commands.config import show_config
from .commands.diff import setup_diff_parser
from .commands.index import setup_index_parser
from .commands.monitor import setup_monitor_parser
from .commands.related import setup_related_parser
from .commands.service import setup_service_parser
from .commands.transform import setup_transform_parser
from .commands.vault import setup_vault_parser


def main(argv: Optional[List[str]] = None) -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(prog="wks0", description="WKS management CLI")
    sub = parser.add_subparsers(dest="cmd")
    
    # Global display mode
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
    version_str = f"wks0 {pkg_version}"
    if git_sha:
        version_str = f"{version_str} ({git_sha})"
    parser.add_argument(
        "--version",
        action="version",
        version=version_str,
        help="Show CLI version and exit",
    )
    
    # Add --display argument (cli or mcp, auto-detected)
    add_display_argument(parser)

    # Config command - show config file
    cfg = sub.add_parser("config", help="Show configuration file")
    cfg.set_defaults(func=show_config)

    # Setup command parsers
    setup_service_parser(sub)
    setup_monitor_parser(sub)
    setup_index_parser(sub)
    setup_related_parser(sub)
    setup_diff_parser(sub)
    setup_transform_parser(sub)
    setup_vault_parser(sub)
    
    # DB command (from cli_db module)
    from .. import cli_db
    db_parser = cli_db.setup_db_parser(sub)
    
    # MCP server command
    mcp = sub.add_parser("mcp", help="MCP (Model Context Protocol) server for AI integration")
    mcpsub = mcp.add_subparsers(dest="mcp_cmd")
    mcprun = mcpsub.add_parser("run", help="Start MCP server (stdio transport)")
    mcprun.add_argument(
        "--direct",
        action="store_true",
        help="Bypass the background broker and run the MCP server inline.",
    )
    
    def mcp_run(args: argparse.Namespace) -> int:
        """Start MCP server for AI integration."""
        if not args.direct:
            socket_path = mcp_socket_path()
            if proxy_stdio_to_socket(socket_path):
                return 0
        from ..mcp_server import main as mcp_main
        mcp_main()
        return 0
    mcprun.set_defaults(func=mcp_run)

    mcpinstall = mcpsub.add_parser(
        "install", help="Register the WKS MCP server with supported clients"
    )
    mcpinstall.add_argument(
        "--command-path",
        dest="command_path",
        help="Optional override for the MCP executable (defaults to resolved wks0).",
    )
    mcpinstall.add_argument(
        "--client",
        dest="clients",
        action="append",
        choices=["cursor", "claude", "gemini"],
        help="Limit installation to a specific client. Repeatable; default installs to all.",
    )

    def mcp_install(args: argparse.Namespace) -> int:
        from ..mcp_setup import install_mcp_configs

        results = install_mcp_configs(
            clients=args.clients,
            command_override=args.command_path,
        )
        for res in results:
            prefix = f"[{res.client}] {res.status.upper()}"
            print(f"{prefix}: {res.message or ''}".rstrip())
        return 0

    mcpinstall.set_defaults(func=mcp_install)

    # Parse arguments
    args = parser.parse_args(argv)
    
    # Auto-detect display mode if not specified
    if not hasattr(args, "display") or args.display is None:
        args.display = "cli"  # Default to CLI
    
    # Get display object
    args.display_obj = get_display(args.display)

    # Handle no command - show help for command groups
    if not hasattr(args, "func"):
        help_registry = {
            'config': cfg,
            'service': None,  # Will be set by setup_service_parser
            'monitor': None,  # Will be set by setup_monitor_parser
            'db': db_parser,
            'mcp': mcp,
        }
        cmd = getattr(args, 'cmd', None)
        if cmd == 'config':
            cfg.print_help()
            return 2
        elif cmd == 'db':
            db_parser.print_help()
            return 2
        elif cmd == 'mcp':
            mcp.print_help()
            return 2
        parser.print_help()
        return 2

    # Execute command
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
