"""Helper functions for vault commands - reduces complexity."""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def prepare_file_and_vault_paths(args, cfg, display) -> Optional[Tuple[Path, Path, Path]]:
    """Prepare and validate file and vault paths.

    Returns:
        Tuple of (file_path, vault_path, expanded_vault_path) or None if validation fails
    """
    from ...utils import expand_path

    vault_path_str = cfg.vault.base_dir
    if not vault_path_str:
        if display:
            display.error("vault.base_dir not configured")
        else:
            print("Error: vault.base_dir not configured")
        return None

    vault_path = expand_path(vault_path_str)
    file_path = expand_path(args.file_path)

    if not file_path.exists():
        if display:
            display.error(f"File does not exist: {file_path}")
        else:
            print(f"Error: File does not exist: {file_path}")
        return None

    return file_path, Path(vault_path_str), vault_path


def check_monitoring_status(cfg, file_path: Path) -> Tuple[bool, Optional[int]]:
    """Check if file is monitored and get its priority.

    Returns:
        Tuple of (is_monitored, priority)
    """
    from ...monitor import MonitorController

    try:
        monitor_info = MonitorController.check_path(cfg, str(file_path))
        is_monitored = monitor_info.get("is_monitored", False)
        priority = monitor_info.get("priority", 0) if is_monitored else None
        return is_monitored, priority
    except Exception:
        return False, None


def prepare_target_uris(file_path: Path, vault_path: Path) -> Tuple[str, str, bool]:
    """Convert file path to URI and prepare variants.

    Returns:
        Tuple of (target_uri, target_uri_no_ext, is_external)
    """
    from ...uri_utils import convert_to_uri

    target_uri = convert_to_uri(file_path, vault_path)
    is_external = not target_uri.startswith("vault:///")

    if target_uri.endswith('.md'):
        target_uri_no_ext = target_uri[:-3]
    else:
        target_uri_no_ext = target_uri

    return target_uri, target_uri_no_ext, is_external


def query_vault_links(coll, target_uri: str, target_uri_no_ext: str, show_from: bool, show_to: bool) -> Tuple[List[Dict], List[Dict]]:
    """Query vault database for links FROM and TO the target file.

    Returns:
        Tuple of (links_from, links_to)
    """
    links_from = []
    links_to = []

    if show_from:
        from_query = {
            "doc_type": "link",
            "$or": [
                {"from_uri": target_uri},
                {"from_uri": target_uri_no_ext}
            ]
        }
        links_from = list(coll.find(from_query))

    if show_to:
        to_query = {
            "doc_type": "link",
            "$or": [
                {"to_uri": target_uri},
                {"to_uri": target_uri_no_ext}
            ]
        }
        links_to = list(coll.find(to_query))

    return links_from, links_to


def fallback_scan_vault(vault_path: Path, vault_cfg: Dict, target_uri: str, target_uri_no_ext: str,
                        show_from: bool, show_to: bool, links_from: List[Dict], links_to: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    """Scan vault markdown directly if DB has no matches.

    Returns:
        Tuple of (links_from, links_to) with fallback data filled in
    """
    from ...vault.obsidian import ObsidianVault
    from ...vault.indexer import VaultLinkScanner

    try:
        fallback_vault = ObsidianVault(vault_path, base_dir=vault_cfg.vault.wks_dir)
        scanner = VaultLinkScanner(fallback_vault)
        records = scanner.scan()

        if show_from and not links_from:
            links_from = [
                {
                    "to_uri": rec.to_uri,
                    "link_type": rec.link_type,
                    "line_number": rec.line_number,
                    "alias_or_text": rec.alias_or_text,
                    "source_heading": rec.source_heading,
                    "raw_line": rec.raw_line,
                }
                for rec in records
                if rec.from_uri in (target_uri, target_uri_no_ext)
            ]

        if show_to and not links_to:
            links_to = [
                {
                    "from_uri": rec.from_uri,
                    "link_type": rec.link_type,
                    "line_number": rec.line_number,
                    "source_heading": rec.source_heading,
                    "raw_line": rec.raw_line,
                }
                for rec in records
                if rec.to_uri in (target_uri, target_uri_no_ext)
            ]
    except Exception:
        pass

    return links_from, links_to


def display_links_with_display_obj(display, target_uri: str, is_monitored: bool, priority: Optional[int],
                                    show_from: bool, links_from: List[Dict], show_to: bool, links_to: List[Dict]) -> None:
    """Display link results using display object."""
    display.info(f"Links for: {target_uri}")
    if is_monitored and priority is not None:
        display.success(f"✓ File IS monitored (priority: {priority})")
    else:
        display.warning(f"✗ File NOT monitored")
    display.info("")

    if show_from:
        display.info(f"Links FROM this file ({len(links_from)}):")
        if links_from:
            for link in links_from:
                to_display = link.get('to_uri', '-')
                link_type = link.get('link_type', '-')
                line_num = link.get('line_number', '-')
                alias = link.get('alias_or_text', '')
                alias_str = f" (alias: {alias})" if alias else ""
                display.info(f"  → {to_display} [{link_type}] (line {line_num}){alias_str}")
        else:
            display.warning("  (no outgoing links)")

    if show_to:
        display.info(f"\nLinks TO this file ({len(links_to)}):")
        if links_to:
            for link in links_to:
                from_display = link.get('from_uri', '-')
                link_type = link.get('link_type', '-')
                line_num = link.get('line_number', '-')
                heading = link.get('source_heading', '')
                heading_str = f" (in section: {heading})" if heading else ""
                display.info(f"  ← {from_display} [{link_type}] (line {line_num}){heading_str}")
        else:
            display.warning("  (no incoming links)")


def display_links_plain_text(target_uri: str, is_monitored: bool, priority: Optional[int],
                             show_from: bool, links_from: List[Dict], show_to: bool, links_to: List[Dict]) -> None:
    """Display link results as plain text."""
    print(f"Links for: {target_uri}")
    if is_monitored and priority is not None:
        print(f"✓ File IS monitored (priority: {priority})")
    else:
        print(f"✗ File NOT monitored")
    print()

    if show_from:
        print(f"Links FROM this file ({len(links_from)}):")
        if links_from:
            for link in links_from:
                to_display = link.get('to_uri', '-')
                link_type = link.get('link_type', '-')
                line_num = link.get('line_number', '-')
                alias = link.get('alias_or_text', '')
                alias_str = f" (alias: {alias})" if alias else ""
                print(f"  → {to_display} [{link_type}] (line {line_num}){alias_str}")
        else:
            print("  (no outgoing links)")

    if show_to:
        print(f"\nLinks TO this file ({len(links_to)}):")
        if links_to:
            for link in links_to:
                from_display = link.get('from_uri', '-')
                link_type = link.get('link_type', '-')
                line_num = link.get('line_number', '-')
                heading = link.get('source_heading', '')
                heading_str = f" (in section: {heading})" if heading else ""
                print(f"  ← {from_display} [{link_type}] (line {link_num}){heading_str}")
        else:
            print("  (no incoming links)")


# Vault validation helpers

def prepare_vault_for_validation(cfg: Dict, display: Any) -> Optional[Tuple[Path, str]]:
    """Prepare vault path and base_dir for validation.

    Returns:
        Tuple of (vault_path, base_dir) or None if validation fails
    """
    from ...utils import expand_path

    vault_path_str = cfg.vault.base_dir
    if not vault_path_str:
        if display:
            display.error("vault.base_dir not configured")
        else:
            print("Error: vault.base_dir not configured")
        return None

    vault_path = expand_path(vault_path_str)
    base_dir = cfg.vault.wks_dir
    return vault_path, base_dir


def scan_vault_for_broken_links(vault_path: Path, base_dir: str) -> Tuple[Any, Any, List[Any], Dict[str, List[Any]]]:
    """Scan vault and collect broken links.

    Returns:
        Tuple of (records, stats, broken_links, broken_by_status)
    """
    from ...vault.obsidian import ObsidianVault
    from ...vault.indexer import VaultLinkScanner

    vault = ObsidianVault(vault_path, base_dir=base_dir)
    scanner = VaultLinkScanner(vault)
    records = scanner.scan()
    stats = scanner.stats

    broken_links = [r for r in records if r.status != "ok"]
    broken_by_status = {}
    for record in broken_links:
        broken_by_status.setdefault(record.status, []).append(record)

    return records, stats, broken_links, broken_by_status


def display_validation_results_rich(display: Any, stats: Any, broken_links: List, broken_by_status: Dict) -> int:
    """Display validation results using display object."""
    display.info(f"Scanned {stats.notes_scanned} notes, found {stats.edge_total} links")

    if not broken_links:
        display.success("✓ All links valid!")
        return 0

    display.error(f"✗ Found {len(broken_links)} broken link(s)")

    for status, links in broken_by_status.items():
        display.warning(f"\n{status.upper()} ({len(links)} links):")
        for link in links[:10]:  # Limit to 10 per status
            display.info(f"  {link.note_path}:{link.line_number} → [[{link.raw_target}]]")
        if len(links) > 10:
            display.info(f"  ... and {len(links) - 10} more")

    return 1


def display_validation_results_plain(stats: Any, broken_links: List, broken_by_status: Dict) -> int:
    """Display validation results as plain text."""
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
