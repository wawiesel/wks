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


def _format_age(iso_value: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_value.replace("Z", "+00:00"))
    except Exception:
        return iso_value
    delta = datetime.now(timezone.utc) - dt
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return f"{iso_value} ({seconds}s ago)"
    minutes = seconds // 60
    if minutes < 60:
        return f"{iso_value} ({minutes}m ago)"
    hours = minutes // 60
    return f"{iso_value} ({hours}h ago)"


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

    if getattr(args, "display") == "cli" and hasattr(display, "console"):
        _render_cli_vault_status(display, summary)
    else:
        rows = [
            {"Metric": "Total links", "Value": str(summary.total_links)},
            {"Metric": "OK", "Value": str(summary.ok_links)},
            {"Metric": "Missing symlink", "Value": str(summary.missing_symlink)},
            {"Metric": "Missing target", "Value": str(summary.missing_target)},
            {"Metric": "Legacy links", "Value": str(summary.legacy_links)},
            {"Metric": "External URLs", "Value": str(summary.external_urls)},
            {"Metric": "Embeds", "Value": str(summary.embeds)},
            {"Metric": "Wiki links", "Value": str(summary.wiki_links)},
            {"Metric": "Notes scanned", "Value": str(summary.notes_scanned)},
        ]
        if summary.last_sync:
            rows.append({"Metric": "Last sync", "Value": _format_age(summary.last_sync)})
        if summary.scan_duration_ms is not None:
            rows.append({"Metric": "Scan duration", "Value": f"{summary.scan_duration_ms} ms"})
        display.table(rows, headers=["Metric", "Value"], title="Vault Link Status")

        if summary.issues:
            issue_rows = []
            for issue in summary.issues:
                issue_rows.append(
                    {
                        "Note": issue.note_path,
                        "Line": str(issue.line_number),
                        "Target": issue.target_uri,
                        "Status": issue.status,
                        "Updated": issue.last_updated or "-",
                    }
                )
            display.table(issue_rows, title="Unhealthy Links", headers=["Note", "Line", "Target", "Status", "Updated"])

    if summary.errors:
        for err in summary.errors:
            display.warning(f"Scanner: {err}")

    return 0


def _render_cli_vault_status(display, summary):
    from rich.table import Table
    from rich.panel import Panel
    from rich.columns import Columns

    summary_table = Table(show_header=False, box=None, padding=(0, 1))
    summary_table.add_column("Metric", justify="left", style="cyan")
    summary_table.add_column("Value", justify="right")

    metrics = [
        ("Total links", summary.total_links),
        ("OK", summary.ok_links),
        ("Missing symlink", summary.missing_symlink),
        ("Missing target", summary.missing_target),
        ("Legacy links", summary.legacy_links),
        ("Notes scanned", summary.notes_scanned),
    ]
    if summary.last_sync:
        metrics.append(("Last sync", _format_age(summary.last_sync)))
    if summary.scan_duration_ms is not None:
        metrics.append(("Scan duration", f"{summary.scan_duration_ms} ms"))
    for label, value in metrics:
        summary_table.add_row(label, str(value))

    types_table = Table(show_header=False, box=None, padding=(0, 1))
    types_table.add_column("Type", justify="left", style="magenta")
    types_table.add_column("Count", justify="right")
    types = [
        ("Embeds", summary.embeds),
        ("Wiki links", summary.wiki_links),
        ("External URLs", summary.external_urls),
    ]
    for label, value in types:
        types_table.add_row(label, str(value))

    columns = Columns([summary_table, types_table], equal=True, expand=True)
    display.console.print(Panel.fit(columns, title="Vault Status", border_style="cyan", width=MAX_DISPLAY_WIDTH))

    if summary.issues:
        issue_table = Table(title="", show_header=True, header_style="bold red")
        issue_table.add_column("Note", justify="left")
        issue_table.add_column("Line", justify="right")
        issue_table.add_column("Target", justify="left")
        issue_table.add_column("Status", justify="center")
        issue_table.add_column("Updated", justify="right")
        for issue in summary.issues:
            issue_table.add_row(
                issue.note_path,
                str(issue.line_number),
                issue.target_uri,
                issue.status,
                issue.last_updated or "-",
            )
        display.console.print(Panel.fit(issue_table, title="Unhealthy Links", border_style="red", width=MAX_DISPLAY_WIDTH))
    else:
        display.console.print(
            Panel.fit(
                "[dim]No unhealthy links detected[/dim]",
                title="Unhealthy Links",
                border_style="green",
                width=MAX_DISPLAY_WIDTH,
            )
        )


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
