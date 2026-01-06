"""Vault check API command.

CLI: wksc vault check [path]
MCP: wksm_vault_check
"""

from collections.abc import Iterator
from typing import Any

from ..config._ensure_arg_uri import _ensure_arg_uri
from ..config.StageResult import StageResult
from ..config.URI import URI
from . import VaultCheckOutput


def cmd_check(uri: URI | None = None) -> StageResult:
    """Validate link targets in vault markdown files.

    Performs a live scan of the vault (not database lookup) to verify
    that all markdown link targets resolve to existing files. This detects:
    - Broken internal links (missing target files)
    - Malformed link syntax
    - Links that cannot be resolved

    Args:
        uri: URI to check. If None, checks all markdown files in vault.

    Returns:
        StageResult with VaultCheckOutput containing validation results
        including list of broken links with file, line number, and status.
    """

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        from ..config.WKSConfig import WKSConfig
        from ._constants import STATUS_OK
        from ._obsidian._Scanner import _Scanner
        from .Vault import Vault

        yield (0.1, "Loading configuration...")
        try:
            config: Any = WKSConfig.load()
            base_dir = config.vault.base_dir
            if not base_dir:
                raise ValueError("vault.base_dir not configured")
        except Exception as e:
            result_obj.output = VaultCheckOutput(
                errors=[f"Failed to load config: {e}"],
                warnings=[],
                path=str(uri) if uri else None,
                notes_checked=0,
                links_checked=0,
                broken_count=0,
                issues=[],
                is_valid=False,
                success=False,
            ).model_dump(mode="python")
            result_obj.result = f"Vault check failed: {e}"
            result_obj.success = False
            return

        yield (0.2, "Initializing vault...")
        try:
            with Vault(config.vault) as vault:
                scanner = _Scanner(vault)
                yield (0.3, "Scanning vault for links...")
                # If uri specified, scan only that file
                files_to_scan = None
                if uri:
                    file_path = _ensure_arg_uri(
                        uri,
                        result_obj,
                        VaultCheckOutput,
                        vault_path=vault.vault_path,
                        uri_field="path",
                        notes_checked=0,
                        links_checked=0,
                        broken_count=0,
                        issues=[],
                        is_valid=False,
                        success=False,
                    )
                    if not file_path:
                        return
                    files_to_scan = [file_path]

                yield (0.5, "Checking link health...")
                records = scanner.scan(files=files_to_scan)
                stats = scanner.stats

                # Build issues list from scanner records (live scan results)
                # Records have status from the scanner's link resolution
                issues = []
                for record in records:
                    if record.status != STATUS_OK:
                        issues.append(
                            {
                                "from_uri": record.from_uri,
                                "line_number": record.line_number,
                                "to_uri": record.to_uri,
                                "status": record.status,
                            }
                        )
                broken_count = len(issues)

                # Errors from stats are strings
                all_errors = list(stats.errors)

                is_valid = broken_count == 0 and len(all_errors) == 0

                result_obj.success = len(all_errors) == 0
                result_obj.output = VaultCheckOutput(
                    path=str(uri) if uri else None,
                    notes_checked=stats.notes_scanned,
                    links_checked=stats.edge_total,
                    broken_count=broken_count,
                    issues=issues,
                    is_valid=is_valid,
                    errors=all_errors,
                    warnings=[],
                    success=result_obj.success,
                ).model_dump(mode="python")

                status_msg = "Health Check Passed" if is_valid else "Health Check Failed"
                result_obj.result = (
                    f"{status_msg}: {stats.notes_scanned} notes, {stats.edge_total} links, {broken_count} broken"
                )

        except Exception as e:
            result_obj.success = False
            result_obj.output = VaultCheckOutput(
                errors=[f"Failed to check vault: {e}"],
                warnings=[],
                path=str(uri) if uri else None,
                notes_checked=0,
                links_checked=0,
                broken_count=0,
                issues=[],
                is_valid=False,
                success=False,
            ).model_dump(mode="python")
            result_obj.result = f"Vault check failed: {e}"
            result_obj.success = False

    announce = f"Checking vault links{f' ({uri})' if uri else ''}..."
    return StageResult(
        announce=announce,
        progress_callback=do_work,
    )
