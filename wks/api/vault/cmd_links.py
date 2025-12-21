"""Vault links API command.

CLI: wksc vault links <path> [--direction to|from|both]
MCP: wksm_vault_links
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any, Literal

from ..database.Database import Database
from ..StageResult import StageResult
from . import VaultLinksOutput


def cmd_links(path: str, direction: Literal["to", "from", "both"] = "both") -> StageResult:
    """Show edges to/from a specific file.

    Args:
        path: File path to query links for (required)
        direction: Link direction - "to", "from", or "both"
    """

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        from ..config.WKSConfig import WKSConfig

        yield (0.1, "Loading configuration...")
        try:
            config: Any = WKSConfig.load()
            # Collection name is just 'vault' - prefix is the DB name
            database_name = "vault"
        except Exception as e:
            result_obj.output = VaultLinksOutput(
                errors=[f"Failed to load config: {e}"],
                warnings=[],
                path=path,
                direction=direction,
                edges=[],
                count=0,
                success=False,
            ).model_dump(mode="python")
            result_obj.result = f"Vault links failed: {e}"
            result_obj.success = False
            return

        # Collection name is 'link' - prefix is the DB name
        database_name = "edges"
        yield (0.3, "Resolving vault path...")
        try:
            # Resolve path to vault:/// URI using CWD-aware logic
            from wks.utils.resolve_vault_path import VaultPathError, resolve_vault_path

            vault_base = Path(config.vault.base_dir).expanduser().resolve()
            try:
                uri, _abs_path = resolve_vault_path(path, vault_base)
            except VaultPathError as e:
                result_obj.output = VaultLinksOutput(
                    errors=[str(e)],
                    warnings=[],
                    path=path,
                    direction=direction,
                    edges=[],
                    count=0,
                    success=False,
                ).model_dump(mode="python")
                result_obj.result = str(e)
                result_obj.success = False
                return

            yield (0.4, "Querying vault database...")
            with Database(config.database, database_name) as database:
                # Filter for vault domain: links with from_local_uri starting with vault:///
                vault_filter = {"from_local_uri": {"$regex": "^vault:///"}}

                # Build query based on direction
                query: dict[str, Any] = {}
                if direction == "from":
                    query = {**vault_filter, "from_local_uri": uri}
                elif direction == "to":
                    query = {**vault_filter, "to_local_uri": uri}
                elif direction == "both":
                    query = {**vault_filter, "$or": [{"from_local_uri": uri}, {"to_local_uri": uri}]}

                yield (0.6, "Fetching edges...")
                cursor = database.find(
                    query,
                    {"from_local_uri": 1, "to_local_uri": 1, "line_number": 1},
                )

                edges = [
                    {
                        "from_uri": doc["from_local_uri"],
                        "to_uri": doc["to_local_uri"],
                        "line_number": doc.get("line_number", 0),
                    }
                    for doc in list(cursor)[:100]  # Limit to 100
                ]

            yield (1.0, "Complete")
            result_obj.output = VaultLinksOutput(
                errors=[],
                warnings=[],
                path=path,
                direction=direction,
                edges=edges,
                count=len(edges),
                success=True,
            ).model_dump(mode="python")
            result_obj.result = f"Found {len(edges)} edge(s) for {path}"
            result_obj.success = True

        except Exception as e:
            result_obj.output = VaultLinksOutput(
                errors=[f"Query failed: {e}"],
                warnings=[],
                path=path,
                direction=direction,
                edges=[],
                count=0,
                success=False,
            ).model_dump(mode="python")
            result_obj.result = f"Vault links failed: {e}"
            result_obj.success = False

    return StageResult(
        announce=f"Finding links for {path}...",
        progress_callback=do_work,
    )
