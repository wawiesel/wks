"""CLI - thin wrapper on MCP tools.

Per CONTRIBUTING.md: CLI → MCP → API (CLI never calls API directly)
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..display.context import add_display_argument, get_display
from ..mcp_client import proxy_stdio_to_socket
from ..mcp_paths import mcp_socket_path
from ..utils import expand_path, get_package_version


def _call(tool: str, args: Dict[str, Any] = None) -> Dict[str, Any]:
    """Call MCP tool."""
    from ..mcp_server import call_tool

    return call_tool(tool, args or {})


def _out(data: Any, display) -> None:
    """Output result."""
    if isinstance(data, dict):
        display.json_output(data)
    else:
        print(data)


def _err(result: Dict) -> int:
    """Print errors, return exit code."""
    for msg in result.get("messages", []):
        print(f"{msg.get('type', 'error')}: {msg.get('text', '')}", file=sys.stderr)
    return 0 if result.get("success", True) else 1


# =============================================================================
# Commands: config, transform, cat, diff
# =============================================================================


def _cmd_config(args: argparse.Namespace) -> int:
    r = _call("wksm_config")
    _out(r.get("data", r), args.display_obj)
    return _err(r)


def _cmd_transform(args: argparse.Namespace) -> int:
    path = expand_path(args.file_path)
    if not path.exists():
        print(f"Error: File not found: {path}", file=sys.stderr)
        return 2
    r = _call("wksm_transform", {"file_path": str(path), "engine": args.engine, "options": {}})
    if r.get("success"):
        print(r.get("data", {}).get("checksum", ""))
    return _err(r)


def _cmd_cat(args: argparse.Namespace) -> int:
    r = _call("wksm_cat", {"target": args.input})
    if r.get("success"):
        content = r.get("data", {}).get("content", "")
        if args.output:
            Path(args.output).write_text(content)
            print(f"Saved to {args.output}", file=sys.stderr)
        else:
            print(content)
    return _err(r)


def _cmd_diff(args: argparse.Namespace) -> int:
    r = _call("wksm_diff", {"engine": args.engine, "target_a": args.file1, "target_b": args.file2})
    if r.get("success"):
        print(r.get("data", {}).get("diff", ""))
    return _err(r)


# =============================================================================
# Monitor commands
# =============================================================================


def _cmd_monitor_status(args: argparse.Namespace) -> int:
    _out(_call("wksm_monitor_status"), args.display_obj)
    return 0


def _cmd_monitor_check(args: argparse.Namespace) -> int:
    _out(_call("wksm_monitor_check", {"path": args.path}), args.display_obj)
    return 0


def _cmd_monitor_validate(args: argparse.Namespace) -> int:
    r = _call("wksm_monitor_validate")
    _out(r, args.display_obj)
    return 1 if r.get("issues") else 0


def _cmd_monitor_list(args: argparse.Namespace) -> int:
    _out(_call("wksm_monitor_list", {"list_name": args.list_name}), args.display_obj)
    return 0


def _cmd_monitor_add(args: argparse.Namespace) -> int:
    r = _call("wksm_monitor_add", {"list_name": args.list_name, "value": args.value})
    print(f"{'Added' if r.get('success') else 'Failed'}: {args.value}", file=sys.stderr)
    return 0 if r.get("success") else 1


def _cmd_monitor_remove(args: argparse.Namespace) -> int:
    r = _call("wksm_monitor_remove", {"list_name": args.list_name, "value": args.value})
    print(f"{'Removed' if r.get('success') else 'Failed'}: {args.value}", file=sys.stderr)
    return 0 if r.get("success") else 1


def _cmd_monitor_managed_list(args: argparse.Namespace) -> int:
    _out(_call("wksm_monitor_managed_list"), args.display_obj)
    return 0


def _cmd_monitor_managed_add(args: argparse.Namespace) -> int:
    r = _call("wksm_monitor_managed_add", {"path": args.path, "priority": args.priority})
    print(f"{'Added' if r.get('success') else 'Failed'}", file=sys.stderr)
    return 0 if r.get("success") else 1


def _cmd_monitor_managed_remove(args: argparse.Namespace) -> int:
    r = _call("wksm_monitor_managed_remove", {"path": args.path})
    print(f"{'Removed' if r.get('success') else 'Failed'}", file=sys.stderr)
    return 0 if r.get("success") else 1


def _cmd_monitor_managed_priority(args: argparse.Namespace) -> int:
    r = _call("wksm_monitor_managed_set_priority", {"path": args.path, "priority": args.priority})
    print(f"{'Updated' if r.get('success') else 'Failed'}", file=sys.stderr)
    return 0 if r.get("success") else 1


# =============================================================================
# Vault commands
# =============================================================================


def _cmd_vault_status(args: argparse.Namespace) -> int:
    _out(_call("wksm_vault_status"), args.display_obj)
    return 0


def _cmd_vault_sync(args: argparse.Namespace) -> int:
    r = _call("wksm_vault_sync", {"batch_size": getattr(args, "batch_size", 1000)})
    _out(r, args.display_obj)
    return 0


def _cmd_vault_validate(args: argparse.Namespace) -> int:
    _out(_call("wksm_vault_validate"), args.display_obj)
    return 0


def _cmd_vault_fix_symlinks(args: argparse.Namespace) -> int:
    _out(_call("wksm_vault_fix_symlinks"), args.display_obj)
    return 0


def _cmd_vault_links(args: argparse.Namespace) -> int:
    r = _call(
        "wksm_vault_links",
        {"file_path": args.path, "direction": getattr(args, "direction", "both")},
    )
    _out(r, args.display_obj)
    return 0


# =============================================================================
# DB commands
# =============================================================================


def _cmd_db_monitor(args: argparse.Namespace) -> int:
    """Query monitor database via MCP."""
    r = _call("wksm_db_monitor", {})
    _out(r, args.display_obj)
    return _err(r)


def _cmd_db_vault(args: argparse.Namespace) -> int:
    """Query vault database via MCP."""
    r = _call("wksm_db_vault", {})
    _out(r, args.display_obj)
    return _err(r)


def _cmd_db_transform(args: argparse.Namespace) -> int:
    """Query transform database via MCP."""
    r = _call("wksm_db_transform", {})
    _out(r, args.display_obj)
    return _err(r)


# =============================================================================
# Service commands
# =============================================================================


def _cmd_service_status(args: argparse.Namespace) -> int:
    """Show daemon/service status via MCP."""
    r = _call("wksm_service", {})
    _out(r.get("data", r), args.display_obj)
    return _err(r)


# =============================================================================
# Parser setup
# =============================================================================


def _setup_monitor(sub):
    LISTS = [
        "include_paths",
        "exclude_paths",
        "include_dirnames",
        "exclude_dirnames",
        "include_globs",
        "exclude_globs",
    ]

    mon = sub.add_parser("monitor", help="Monitor operations")
    m = mon.add_subparsers(dest="monitor_cmd")

    m.add_parser("status").set_defaults(func=_cmd_monitor_status)
    p = m.add_parser("check")
    p.add_argument("path")
    p.set_defaults(func=_cmd_monitor_check)
    m.add_parser("validate").set_defaults(func=_cmd_monitor_validate)

    for name in LISTS:
        p = m.add_parser(name)
        s = p.add_subparsers(dest=f"{name}_cmd")
        s.add_parser("list").set_defaults(func=_cmd_monitor_list, list_name=name)
        a = s.add_parser("add")
        a.add_argument("value")
        a.set_defaults(func=_cmd_monitor_add, list_name=name)
        r = s.add_parser("remove")
        r.add_argument("value")
        r.set_defaults(func=_cmd_monitor_remove, list_name=name)

    mg = m.add_parser("managed")
    ms = mg.add_subparsers(dest="managed_cmd")
    ms.add_parser("list").set_defaults(func=_cmd_monitor_managed_list)
    a = ms.add_parser("add")
    a.add_argument("path")
    a.add_argument("priority", type=int)
    a.set_defaults(func=_cmd_monitor_managed_add)
    r = ms.add_parser("remove")
    r.add_argument("path")
    r.set_defaults(func=_cmd_monitor_managed_remove)
    p = ms.add_parser("set-priority")
    p.add_argument("path")
    p.add_argument("priority", type=int)
    p.set_defaults(func=_cmd_monitor_managed_priority)


def _setup_vault(sub):
    v = sub.add_parser("vault", help="Vault operations")
    s = v.add_subparsers(dest="vault_cmd")

    s.add_parser("status").set_defaults(func=_cmd_vault_status)
    p = s.add_parser("sync")
    p.add_argument("--batch-size", type=int, default=1000)
    p.set_defaults(func=_cmd_vault_sync)
    s.add_parser("validate").set_defaults(func=_cmd_vault_validate)
    s.add_parser("fix-symlinks").set_defaults(func=_cmd_vault_fix_symlinks)
    p = s.add_parser("links")
    p.add_argument("path")
    p.add_argument("--direction", choices=["both", "to", "from"], default="both")
    p.set_defaults(func=_cmd_vault_links)


def _setup_db(sub):
    db = sub.add_parser("db", help="Database queries")
    s = db.add_subparsers(dest="db_cmd")

    s.add_parser("monitor").set_defaults(func=_cmd_db_monitor)
    s.add_parser("vault").set_defaults(func=_cmd_db_vault)
    s.add_parser("transform").set_defaults(func=_cmd_db_transform)


def _setup_service(sub):
    svc = sub.add_parser("service", help="Service operations")
    s = svc.add_subparsers(dest="service_cmd")

    s.add_parser("status").set_defaults(func=_cmd_service_status)


def main(argv: Optional[List[str]] = None) -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(prog="wksc", description="WKS CLI")
    sub = parser.add_subparsers(dest="cmd")

    # Version
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
    parser.add_argument("--version", action="version", version=f"wksc {v}")
    add_display_argument(parser)

    # Simple commands
    sub.add_parser("config", help="Show config").set_defaults(func=_cmd_config)

    p = sub.add_parser("transform", help="Transform file")
    p.add_argument("engine")
    p.add_argument("file_path")
    p.add_argument("-o", "--output")
    p.set_defaults(func=_cmd_transform)
    p = sub.add_parser("cat", help="Display content")
    p.add_argument("input")
    p.add_argument("-o", "--output")
    p.set_defaults(func=_cmd_cat)
    p = sub.add_parser("diff", help="Compare files")
    p.add_argument("engine")
    p.add_argument("file1")
    p.add_argument("file2")
    p.set_defaults(func=_cmd_diff)

    _setup_monitor(sub)
    _setup_vault(sub)
    _setup_db(sub)
    _setup_service(sub)

    # MCP server
    mcp = sub.add_parser("mcp", help="MCP server")
    ms = mcp.add_subparsers(dest="mcp_cmd")
    run = ms.add_parser("run")
    run.add_argument("--direct", action="store_true")

    def mcp_run(args):
        if not args.direct and proxy_stdio_to_socket(mcp_socket_path()):
            return 0
        from ..mcp_server import main as mcp_main

        mcp_main()
        return 0

    run.set_defaults(func=mcp_run)

    inst = ms.add_parser("install")
    inst.add_argument("--command-path")
    inst.add_argument("--client", dest="clients", action="append", choices=["cursor", "claude", "gemini"])

    def mcp_install(args):
        from ..mcp_setup import install_mcp_configs

        for r in install_mcp_configs(clients=args.clients, command_override=args.command_path):
            print(f"[{r.client}] {r.status.upper()}: {r.message or ''}")
        return 0

    inst.set_defaults(func=mcp_install)

    # Parse and execute
    args = parser.parse_args(argv)
    args.display = getattr(args, "display", None) or "cli"
    args.display_obj = get_display(args.display)

    if not hasattr(args, "func"):
        parser.print_help()
        return 2

    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
