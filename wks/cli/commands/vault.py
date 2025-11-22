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
        result = VaultController.sync_vault(cfg, batch_size=1000)

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


def vault_fix_symlinks_cmd(args: argparse.Namespace) -> int:
    """Auto-create missing _links/ symlinks for all vault references."""
    from pathlib import Path
    from ...vault.obsidian import ObsidianVault
    from ...vault.indexer import VaultLinkScanner
    from ...vault.markdown_parser import parse_wikilinks
    import platform

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
            display.info(f"Scanning vault for missing _links/ symlinks...")

        vault = ObsidianVault(vault_path, base_dir=base_dir)
        links_dir = vault.links_dir
        machine = platform.node().split(".")[0]

        # Collect all _links/ references
        links_to_create = set()
        notes_scanned = 0

        for note_path in vault.iter_markdown_files():
            notes_scanned += 1
            try:
                text = note_path.read_text(encoding="utf-8")
                for link in parse_wikilinks(text):
                    target = link.target
                    if target.startswith("_links/"):
                        # Extract relative path after _links/
                        rel_path = target[len("_links/"):]
                        symlink_path = links_dir / rel_path

                        if not symlink_path.exists():
                            links_to_create.add((rel_path, symlink_path))
            except Exception:
                continue

        if not links_to_create:
            if display:
                display.success(f"✓ All _links/ symlinks exist (scanned {notes_scanned} notes)")
            else:
                print(f"✓ All _links/ symlinks exist (scanned {notes_scanned} notes)")
            return 0

        if display:
            display.info(f"Found {len(links_to_create)} missing symlinks")

        # Try to infer target paths and create symlinks
        created = 0
        failed = []

        for rel_path, symlink_path in sorted(links_to_create):
            # Try to infer the target path
            # Format: machine/path or relative/path
            parts = Path(rel_path).parts

            if len(parts) > 0:
                # Try machine-prefixed path first
                if parts[0] == machine:
                    # This is a machine-specific link: _links/machine/path/to/file
                    target_path = Path("/") / Path(*parts[1:])
                else:
                    # Try as Pictures/ or Documents/ relative path
                    # _links/Pictures/2025-DNCSH_Logos/png/file.png → ~/Pictures/2025-DNCSH_Logos/png/file.png
                    if parts[0] in ["Pictures", "Documents", "Downloads", "Desktop"]:
                        target_path = Path.home() / Path(*parts)
                    else:
                        # Unknown format, skip
                        failed.append((rel_path, "Unknown path format"))
                        continue

                # Check if target exists (file or directory)
                if target_path.exists():
                    # Create symlink parent directories
                    symlink_path.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        symlink_path.symlink_to(target_path)
                        created += 1
                        if display:
                            display.success(f"  Created: {rel_path}")
                    except Exception as exc:
                        failed.append((rel_path, str(exc)))
                else:
                    failed.append((rel_path, f"Target not found: {target_path}"))

        # Display results
        if display:
            if created > 0:
                display.success(f"\n✓ Created {created} symlink(s)")
            if failed:
                display.warning(f"\n✗ Failed to create {len(failed)} symlink(s):")
                for rel_path, reason in failed[:10]:
                    display.info(f"  {rel_path}: {reason}")
                if len(failed) > 10:
                    display.info(f"  ... and {len(failed) - 10} more")
        else:
            if created > 0:
                print(f"✓ Created {created} symlink(s)")
            if failed:
                print(f"✗ Failed to create {len(failed)} symlink(s):")
                for rel_path, reason in failed[:10]:
                    print(f"  {rel_path}: {reason}")
                if len(failed) > 10:
                    print(f"  ... and {len(failed) - 10} more")

        return 0 if not failed else 1

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

    fix_symlinks = vault_sub.add_parser("fix-symlinks", help="Auto-create missing _links/ symlinks")
    fix_symlinks.set_defaults(func=vault_fix_symlinks_cmd)


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
