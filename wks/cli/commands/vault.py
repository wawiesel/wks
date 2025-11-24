"""Vault link commands (status/reporting)."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone

from ...config import load_config
from ...constants import MAX_DISPLAY_WIDTH
from ...vault.status_controller import VaultStatusController
from ..helpers import display_status_table


def _format_age(iso_value: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_value.replace("Z", "+00:00"))
    except Exception:
        return iso_value
    delta = datetime.now(timezone.utc) - dt
    seconds = int(delta.total_seconds())
    if seconds < 60:
        ago = f"{seconds}s"
    else:
        minutes = seconds // 60
        if minutes < 60:
            ago = f"{minutes}m"
        else:
            hours = minutes // 60
            ago = f"{hours}h"
    short = dt.strftime("%Y-%m-%d %H:%M:%S")
    return f"{short} ({ago} ago)"


def _format_cell(text: str) -> str:
    if text is None:
        return "-"
    return str(text)


def _render_vault_status_panel(cfg: dict, title: str = "Vault Status") -> "Panel":
    """Render vault status as a Rich panel (shared by static and live modes)."""
    from rich.panel import Panel
    from rich.table import Table
    from rich.columns import Columns

    controller = VaultStatusController(cfg)
    summary = controller.summarize()
    summary_rows = _build_status_rows(summary)

    # Build table
    key_width = 22
    value_width = 10
    row_tables = []
    for key, value in summary_rows:
        row_table = Table(show_header=False, box=None, padding=(0, 1))
        row_table.add_column("Key", justify="left", width=key_width)
        row_table.add_column("Value", justify="right", width=value_width)
        row_table.add_row(key, value)
        row_tables.append(row_table)

    columns = Columns(row_tables, equal=True, column_first=True)
    return Panel.fit(columns, title=title, border_style="cyan", width=MAX_DISPLAY_WIDTH)


def vault_status_cmd(args: argparse.Namespace) -> int:
    """Render vault status summary."""
    cfg = load_config()

    # JSON output mode
    if getattr(args, "json", False):
        controller = VaultStatusController(cfg)
        try:
            summary = controller.summarize()
        except Exception as exc:
            print(f"Error: {exc}")
            return 2
        print(json.dumps(summary.to_dict(), indent=2))
        return 0

    # Live mode requires CLI display
    live = getattr(args, "live", False)
    if live:
        from rich.console import Console
        from rich.live import Live

        console = Console(width=MAX_DISPLAY_WIDTH)

        def _render_status():
            return _render_vault_status_panel(cfg, title="Vault Status (Live)")

        try:
            with Live(_render_status(), refresh_per_second=0.5, screen=False, console=console) as live_display:
                while True:
                    time.sleep(2.0)
                    try:
                        live_display.update(_render_status())
                    except Exception as update_exc:
                        console.print(f"[yellow]Warning: {update_exc}[/yellow]", end="")
        except KeyboardInterrupt:
            console.print("\n[dim]Stopped monitoring.[/dim]")
            return 0
        except Exception as exc:
            console.print(f"[red]Error in live mode: {exc}[/red]")
            return 2

    # Static mode
    display = getattr(args, "display_obj", None)
    controller = VaultStatusController(cfg)
    try:
        summary = controller.summarize()
    except Exception as exc:
        if display:
            display.error(f"Vault status failed: {exc}")
        else:
            print(f"Error: {exc}")
        return 2

    summary_rows = _build_status_rows(summary)
    display_status_table(display, summary_rows, title="Vault Status")

    if summary.errors:
        _panel_warnings(display, summary.errors)

    return 0


def vault_sync_cmd(args: argparse.Namespace) -> int:
    """Force immediate vault sync to MongoDB."""
    from ...vault import VaultController

    cfg = load_config()
    display = getattr(args, "display_obj", None)

    try:
        if display:
            display.info("Syncing vault links to MongoDB...")
        result = VaultController.sync_vault(cfg, batch_size=1000, incremental=False)

        if display:
            display.success(f"Synced {result['notes_scanned']} notes, {result['edges_written']} edges in {result['sync_duration_ms']}ms")
            if result.get("errors"):
                display.warning(f"{len(result['errors'])} errors during sync")
        return 0
    except Exception as exc:
        if display:
            display.error(f"Vault sync failed: {exc}")
        else:
            print(f"Error: {exc}")
        return 2


def vault_validate_cmd(args: argparse.Namespace) -> int:
    """Validate all vault links (check for broken links)."""
    from pathlib import Path
    from ...vault.obsidian import ObsidianVault
    from ...vault.indexer import VaultLinkScanner

    cfg = load_config()
    display = getattr(args, "display_obj", None)

    try:
        # Get vault configuration
        vault_cfg = cfg.get("vault", {})
        vault_path_str = vault_cfg.get("base_dir")
        if not vault_path_str:
            if display:
                display.error("vault.base_dir not configured")
            else:
                print("Error: vault.base_dir not configured")
            return 2

        from ...utils import expand_path
        vault_path = expand_path(vault_path_str)
        base_dir = vault_cfg.get("wks_dir", "WKS")

        if display:
            display.info(f"Validating vault links in {vault_path}...")

        # Create vault and scanner
        vault = ObsidianVault(vault_path, base_dir=base_dir)
        scanner = VaultLinkScanner(vault)

        # Scan for links
        records = scanner.scan()
        stats = scanner.stats

        # Count broken links
        broken_links = [r for r in records if r.status != "ok"]
        broken_by_status = {}
        for record in broken_links:
            broken_by_status.setdefault(record.status, []).append(record)

        # Display results
        if display:
            display.info(f"Scanned {stats.notes_scanned} notes, found {stats.edge_total} links")

            if not broken_links:
                display.success("✓ All links valid!")
                return 0

            # Show broken links by status
            display.error(f"✗ Found {len(broken_links)} broken link(s)")

            for status, links in broken_by_status.items():
                display.warning(f"\n{status.upper()} ({len(links)} links):")
                for link in links[:10]:  # Limit to 10 per status
                    display.info(f"  {link.note_path}:{link.line_number} → [[{link.raw_target}]]")
                if len(links) > 10:
                    display.info(f"  ... and {len(links) - 10} more")

            return 1  # Exit code 1 for validation failure

        else:
            # Plain text output
            print(f"Scanned {stats.notes_scanned} notes, found {stats.edge_total} links")

            if not broken_links:
                print("✓ All links valid!")
                return 0

            print(f"✗ Found {len(broken_links)} broken link(s)")

            for status, links in broken_by_status.items():
                print(f"\n{status.upper()} ({len(links)} links):")
                for link in links[:10]:
                    print(f"  {link.note_path}:{link.line_number} → [[{link.raw_target}]]")
                if len(links) > 10:
                    print(f"  ... and {len(links) - 10} more")

            return 1

    except Exception as exc:
        if display:
            display.error(f"Vault validation failed: {exc}")
        else:
            print(f"Error: {exc}")
        return 2


def vault_links_cmd(args: argparse.Namespace) -> int:
    """Show all links to and from a specific file."""
    from ...db_helpers import get_vault_db_config, connect_to_mongo
    from .vault_links_helpers import (
        prepare_file_and_vault_paths,
        check_monitoring_status,
        prepare_target_uris,
        query_vault_links,
        fallback_scan_vault,
        display_links_with_display_obj,
        display_links_plain_text,
    )

    cfg = load_config()
    display = getattr(args, "display_obj", None)

    try:
        # Prepare and validate paths
        paths = prepare_file_and_vault_paths(args, cfg, display)
        if not paths:
            return 2
        file_path, vault_path_str, vault_path = paths

        # Check monitoring status
        is_monitored, priority = check_monitoring_status(cfg, file_path)

        # Convert to URIs
        target_uri, target_uri_no_ext, is_external = prepare_target_uris(file_path, vault_path)

        # Determine what to show
        show_from = (not args.to_only) and (not is_external)
        show_to = not args.from_only

        # Query database
        uri, db_name, coll_name = get_vault_db_config(cfg)
        client = connect_to_mongo(uri)
        coll = client[db_name][coll_name]

        links_from, links_to = query_vault_links(coll, target_uri, target_uri_no_ext, show_from, show_to)
        client.close()

        # Fallback to direct scan if DB has no matches
        need_fallback = (show_from and not links_from) or (show_to and not links_to)
        if need_fallback:
            vault_cfg = cfg.get("vault", {})
            links_from, links_to = fallback_scan_vault(
                vault_path, vault_cfg, target_uri, target_uri_no_ext,
                show_from, show_to, links_from, links_to
            )

        # Display results
        if display:
            display_links_with_display_obj(display, target_uri, is_monitored, priority, show_from, links_from, show_to, links_to)
        else:
            display_links_plain_text(target_uri, is_monitored, priority, show_from, links_from, show_to, links_to)

        return 0

    except Exception as exc:
        if display:
            display.error(f"Failed to query links: {exc}")
        else:
            print(f"Error: {exc}")
        return 2


def vault_fix_symlinks_cmd(args: argparse.Namespace) -> int:
    """Rebuild _links/<machine>/ from vault DB (deletes and recreates all symlinks)."""
    from ...vault.obsidian import ObsidianVault
    from ...vault.controller import VaultController
    from ...utils import expand_path

    cfg = load_config()
    display = getattr(args, "display_obj", None)

    try:
        # Get vault configuration
        vault_cfg = cfg.get("vault", {})
        vault_path_str = vault_cfg.get("base_dir")
        if not vault_path_str:
            if display:
                display.error("vault.base_dir not configured")
            else:
                print("Error: vault.base_dir not configured")
            return 2

        vault_path = expand_path(vault_path_str)
        base_dir = vault_cfg.get("wks_dir", "WKS")

        if display:
            display.info(f"Rebuilding _links/ from vault DB...")

        # Initialize vault and controller
        vault = ObsidianVault(vault_path, base_dir=base_dir)
        controller = VaultController(vault)

        # Execute business logic
        result = controller.fix_symlinks()

        # Display results
        if result.links_found == 0:
            if display:
                display.success(f"✓ No file:// links found in vault DB")
            else:
                print(f"✓ No file:// links found in vault DB")
            return 0

        if display:
            display.info(f"Found {result.links_found} file:// links in vault DB")
            if result.created > 0:
                display.success(f"\n✓ Created {result.created} symlink(s)")
            if result.failed:
                display.warning(f"\n✗ Failed to create {len(result.failed)} symlink(s):")
                for rel_path, reason in result.failed[:10]:
                    display.info(f"  {rel_path}: {reason}")
                if len(result.failed) > 10:
                    display.info(f"  ... and {len(result.failed) - 10} more")
        else:
            print(f"Found {result.links_found} file:// links in vault DB")
            if result.created > 0:
                print(f"✓ Created {result.created} symlink(s)")
            if result.failed:
                print(f"✗ Failed to create {len(result.failed)} symlink(s):")
                for rel_path, reason in result.failed[:10]:
                    print(f"  {rel_path}: {reason}")
                if len(result.failed) > 10:
                    print(f"  ... and {len(result.failed) - 10} more")

        return 0 if not result.failed else 1

    except Exception as exc:
        if display:
            display.error(f"Failed to fix symlinks: {exc}")
        else:
            print(f"Error: {exc}")
        return 2


def setup_vault_parser(subparsers) -> None:
    """Register vault command group."""
    vault = subparsers.add_parser("vault", help="Vault link automation commands")
    vault_sub = vault.add_subparsers(dest="vault_cmd")

    def _vault_help(args, parser=vault):
        parser.print_help()
        return 2

    vault.set_defaults(func=_vault_help)

    status = vault_sub.add_parser("status", help="Show Obsidian vault link status")
    status.add_argument("--json", action="store_true", help="Emit raw JSON summary")
    status.add_argument(
        "--live",
        action="store_true",
        help="Keep display updated automatically (refreshes every 2 seconds)"
    )
    status.set_defaults(func=vault_status_cmd)

    sync = vault_sub.add_parser("sync", help="Force immediate vault sync to MongoDB")
    sync.set_defaults(func=vault_sync_cmd)

    validate = vault_sub.add_parser("validate", help="Validate all vault links (check for broken links)")
    validate.set_defaults(func=vault_validate_cmd)

    fix_symlinks = vault_sub.add_parser("fix-symlinks", help="Rebuild _links/<machine>/ from vault DB")
    fix_symlinks.set_defaults(func=vault_fix_symlinks_cmd)

    links = vault_sub.add_parser("links", help="Show all links to and from a specific file")
    links.add_argument("file_path", help="Path to the vault file (e.g., ~/_vault/Projects/XYZ.md)")
    links.add_argument("--to", dest="to_only", action="store_true", help="Show only links TO this file")
    links.add_argument("--from", dest="from_only", action="store_true", help="Show only links FROM this file")
    links.set_defaults(func=vault_links_cmd)


def _build_status_rows(summary):
    rows = [
        ("Total links", str(summary.total_links)),
        ("OK", str(summary.ok_links)),
        ("Missing symlink", str(summary.missing_symlink)),
        ("Missing target", str(summary.missing_target)),
        ("Legacy links", str(summary.legacy_links)),
        ("Notes scanned", str(summary.notes_scanned)),
    ]
    if summary.last_sync:
        rows.append(("Last sync", _format_age(summary.last_sync)))
    if summary.scan_duration_ms is not None:
        rows.append(("Scan duration", f"{summary.scan_duration_ms} ms"))
    rows.append(("", ""))
    rows.append(("Embeds", str(summary.embeds)))
    rows.append(("Wiki links", str(summary.wiki_links)))
    rows.append(("External URLs", str(summary.external_urls)))
    return rows


def _panel_warnings(display, warnings):
    if getattr(display, "console", None):
        from rich.panel import Panel

        content = "\n".join(f"- {_format_cell(msg)}" for msg in warnings)
        display.console.print(Panel.fit(content, title="Scanner Warnings", border_style="yellow", width=MAX_DISPLAY_WIDTH))
    else:
        display.table([{"Warning": _format_cell(msg)} for msg in warnings], headers=["Warning"], title="Scanner Warnings")
