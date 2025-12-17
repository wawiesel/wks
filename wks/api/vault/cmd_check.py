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
                        result_obj.output = {
                            "errors": [f"File not found: {path}"],
                            "notes_checked": 0,
                            "links_checked": 0,
                            "broken_count": 0,
                            "is_valid": False,
                        }
                        return
                    files_to_scan = [file_path]

                yield (0.5, "Checking link health...")
                records = scanner.scan(files=files_to_scan)
                stats = scanner.stats

                # Convert records to edges
                edges = []
                broken_count = 0
                for rec in records:
                    edge = {
                        "from_uri": rec.from_uri,
                        "to_uri": rec.to_uri,
                        "line_number": rec.line_number,
                        "status": rec.status,
                        "raw_target": rec.raw_target,
                    }
                    if rec.status != STATUS_OK:
                        broken_count += 1
                        # edge["error_msg"] = rec.error_msg # Record does not have error_msg
                    edges.append(edge)

                result_obj.success = len(stats.errors) == 0
                result_obj.output = {
                    "notes_checked": stats.notes_scanned,
                    "links_checked": stats.edge_total,
                    "broken_count": broken_count,
                    "is_valid": broken_count == 0 and len(stats.errors) == 0,
                    "errors": [e for e in records if e.status != STATUS_OK],
                    "success": len(stats.errors) == 0,
                }
                if stats.errors and "errors" not in result_obj.output:
                    result_obj.output["errors"] = []

        except Exception as e:
            result_obj.success = False
            result_obj.output = {
                "errors": [f"Failed to check vault: {e}"],
                "notes_checked": 0,
                "links_checked": 0,
                "broken_count": 0,
                "is_valid": False,
            }
            result_obj.result = f"Vault check failed: {e}"
            result_obj.success = False

    announce = f"Checking vault links{f' ({path})' if path else ''}..."
    return StageResult(
        announce=announce,
        progress_callback=do_work,
    )
