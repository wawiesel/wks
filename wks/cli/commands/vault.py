"""Vault link commands (status/reporting)."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from ...config import load_config
from ...constants import MAX_DISPLAY_WIDTH
from ...vault import load_vault
from ...vault.indexer import VaultLinkIndexer
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


def vault_status_cmd(args: argparse.Namespace) -> int:
    """Render vault status summary."""
    cfg = load_config()
    display = getattr(args, "display_obj", None)
    try:
        vault = load_vault(cfg)
        indexer = VaultLinkIndexer.from_config(vault, cfg)
        indexer.sync()
    except Exception as exc:
        if display:
            display.error(f"Vault scan failed: {exc}")
        else:
            print(f"Error: {exc}")
        return 2
    controller = VaultStatusController(cfg)
    try:
        summary = controller.summarize()
    except Exception as exc:
        if display:
            display.error(f"Vault status failed: {exc}")
        else:
            print(f"Error: {exc}")
        return 2

    if getattr(args, "json", False):
        print(json.dumps(summary.to_dict(), indent=2))
        return 0

    summary_rows = _build_status_rows(summary)
    display_status_table(display, summary_rows, title="Vault Status")

    if summary.errors:
        _panel_warnings(display, summary.errors)

    return 0


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
    status.set_defaults(func=vault_status_cmd)


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
