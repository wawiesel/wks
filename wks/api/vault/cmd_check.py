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
        from ...utils import expand_path
        from ..config.WKSConfig import WKSConfig
        from ._constants import STATUS_OK
        from ._obsidian._Impl import _Impl as ObsidianVault
        from ._obsidian._Scanner import _Scanner

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
            vault = ObsidianVault(expand_path(base_dir))
            scanner = _Scanner(vault)
        except Exception as e:
            result_obj.output = VaultCheckOutput(
                errors=[f"Failed to initialize vault: {e}"],
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

        yield (0.3, "Scanning vault for links...")
        try:
            # If path specified, scan only that file
            files_to_scan = None
            if path:
                file_path = Path(path).expanduser().resolve()
                if not file_path.exists():
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
                    result_obj.result = "Vault check failed: file not found"
                    result_obj.success = False
                    return
                files_to_scan = [file_path]

            yield (0.5, "Checking link health...")
            records = scanner.scan(files=files_to_scan)
            stats = scanner.stats

            # Find broken links
            broken = [r for r in records if r.status != STATUS_OK]
            issues = [
                {
                    "note_path": r.note_path,
                    "line_number": r.line_number,
                    "target_uri": r.to_uri,
                    "status": r.status,
                }
                for r in broken[:50]  # Limit to 50 issues
            ]

            yield (1.0, "Complete")
            is_valid = len(broken) == 0
            result_obj.output = VaultCheckOutput(
                errors=stats.errors,
                warnings=[],
                path=path,
                notes_checked=stats.notes_scanned,
                links_checked=stats.edge_total,
                broken_count=len(broken),
                issues=issues,
                is_valid=is_valid,
                success=True,
            ).model_dump(mode="python")
            msg = "valid" if is_valid else f"{len(broken)} issues"
            result_obj.result = f"Checked {stats.notes_scanned} notes: {msg}"
            result_obj.success = True

        except Exception as e:
            result_obj.output = VaultCheckOutput(
                errors=[f"Check failed: {e}"],
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
