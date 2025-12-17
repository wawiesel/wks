"""Vault check API command.

CLI: wksc vault check [path]
MCP: wksm_vault_check
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from ..StageResult import StageResult
from . import VaultCheckOutput


def cmd_check(path: str | None = None) -> StageResult:
    """Check vault link health.

    Args:
        path: Optional file path to check. If None, check entire vault.
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
                path=path,
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
                # If path specified, scan only that file
                files_to_scan = None
                if path:
                    file_path = Path(path).expanduser().resolve()
                    if not file_path.exists():
                        result_obj.success = False
                        result_obj.output = VaultCheckOutput(
                            errors=[f"File not found: {path}"],
                            warnings=[],
                            path=path,
                            notes_checked=0,
                            links_checked=0,
                            broken_count=0,
                            issues=[],
                            is_valid=False,
                            success=False,
                        ).model_dump(mode="python")
                        result_obj.result = f"File not found: {path}"
                        return
                    files_to_scan = [file_path]

                yield (0.5, "Checking link health...")
                records = scanner.scan(files=files_to_scan)
                stats = scanner.stats

                # Convert records to issues
                issues = []
                broken_count = 0
                for rec in records:
                    if rec.status != STATUS_OK:
                        broken_count += 1
                        issues.append(
                            {
                                "note_path": rec.note_path,
                                "line_number": rec.line_number,
                                "target_uri": rec.to_uri,
                                "status": rec.status,
                            }
                        )

                # Errors from stats are strings
                all_errors = list(stats.errors)

                is_valid = broken_count == 0 and len(all_errors) == 0

                result_obj.success = len(all_errors) == 0
                result_obj.output = VaultCheckOutput(
                    path=path,
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
                path=path,
                notes_checked=0,
                links_checked=0,
                broken_count=0,
                issues=[],
                is_valid=False,
                success=False,
            ).model_dump(mode="python")
            result_obj.result = f"Vault check failed: {e}"
            result_obj.success = False

    announce = f"Checking vault links{f' ({path})' if path else ''}..."
    return StageResult(
        announce=announce,
        progress_callback=do_work,
    )
