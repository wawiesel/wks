"""Vault status API command.

CLI: wksc vault status
MCP: wksm_vault_status
"""

from collections.abc import Iterator
from typing import Any

from ..database.Database import Database
from ..StageResult import StageResult
from ..utils._write_status_file import write_status_file
from . import VaultStatusOutput


def cmd_status() -> StageResult:
    """Get vault link health status."""

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        from wks.utils.uri_utils import path_to_uri

        from ..config.WKSConfig import WKSConfig
        from ._constants import META_DOCUMENT_ID

        yield (0.1, "Loading configuration...")
        try:
            config: Any = WKSConfig.load()
            wks_home = WKSConfig.get_home_dir()

            # Get vault base URI
            from pathlib import Path

            if not config.vault.base_dir:
                raise ValueError("Vault base_dir not configured")

            vault_base = Path(config.vault.base_dir).resolve()
            vault_base_uri = path_to_uri(vault_base)
            if not vault_base_uri.endswith("/"):
                vault_base_uri += "/"

            # Collection name is 'edges'
            database_name = "edges"
        except Exception as e:
            result_obj.output = VaultStatusOutput(
                errors=[f"Failed to load config: {e}"],
                warnings=[],
                database="",
                total_links=0,
                last_sync=None,
                success=False,
            ).model_dump(mode="python")
            result_obj.result = f"Vault status failed: {e}"
            result_obj.success = False
            return

        yield (0.3, "Querying vault links...")
        try:
            with Database(config.database, database_name) as database:
                # Filter for vault domain: links with from_local_uri starting with vault base URI
                import re

                vault_filter = {"from_local_uri": {"$regex": f"^{re.escape(vault_base_uri)}"}}

                # Count links
                total_links = database.count_documents(vault_filter)

                # Get metadata document (note: meta is still in the same collection but has fixed _id)
                meta = database.find_one({"_id": META_DOCUMENT_ID}) or {}

            yield (1.0, "Complete")
            output = VaultStatusOutput(
                errors=[],
                warnings=[],
                database=database_name,
                total_links=total_links,
                last_sync=meta.get("last_sync"),
                success=True,
            ).model_dump(mode="python")

            # Write status file
            write_status_file(output, wks_home=wks_home, filename="vault.json")

            result_obj.output = output
            result_obj.result = f"Vault status: {total_links} links"
            result_obj.success = True

        except Exception as e:
            result_obj.output = VaultStatusOutput(
                errors=[f"Database query failed: {e}"],
                warnings=[],
                database=database_name,
                total_links=0,
                last_sync=None,
                success=False,
            ).model_dump(mode="python")
            result_obj.result = f"Vault status failed: {e}"
            result_obj.success = False

    return StageResult(
        announce="Checking vault status...",
        progress_callback=do_work,
    )
