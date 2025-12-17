"""Vault links API command.

CLI: wksc vault links <path> [--direction to|from|both]
MCP: wksm_vault_links
"""

from collections.abc import Iterator
from typing import Any, Literal

from ..StageResult import StageResult
from . import VaultLinksOutput


def cmd_links(path: str, direction: Literal["to", "from", "both"] = "both") -> StageResult:
    """Show edges to/from a specific file.

    Args:
        path: File path to query links for (required)
        direction: Link direction - "to", "from", or "both"
    """

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        from pymongo import MongoClient

        from ..config.WKSConfig import WKSConfig
        from ..database._mongo._DbConfigData import _DbConfigData as _MongoDbConfigData
        from ._constants import DOC_TYPE_LINK

        yield (0.1, "Loading configuration...")
        try:
            config: Any = WKSConfig.load()
            if isinstance(config.database.data, _MongoDbConfigData):
                mongo_uri = config.database.data.uri
            else:
                result_obj.output = VaultLinksOutput(
                    errors=[f"Vault requires mongo backend, got {config.database.type}"],
                    warnings=[],
                    path=path,
                    direction=direction,
                    edges=[],
                    count=0,
                    success=False,
                ).model_dump(mode="python")
                result_obj.result = "Vault links failed: unsupported database backend"
                result_obj.success = False
                return

            db_name, coll_name = config.vault.database.split(".", 1)
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

        yield (0.3, "Querying vault database...")
        try:
            client: MongoClient = MongoClient(
                mongo_uri,
                serverSelectionTimeoutMS=5000,
            )
            collection = client[db_name][coll_name]

            # Build URI pattern for the path (normalize to vault:/// format)
            path_uri = path if path.startswith("vault:///") else f"vault:///{path.lstrip('/')}"

            # Build query based on direction
            query: dict[str, Any] = {"doc_type": DOC_TYPE_LINK}
            if direction == "to":
                query["to_uri"] = path_uri
            elif direction == "from":
                query["from_uri"] = path_uri
            else:  # both
                query["$or"] = [{"from_uri": path_uri}, {"to_uri": path_uri}]

            yield (0.6, "Fetching edges...")
            cursor = collection.find(
                query,
                {"from_uri": 1, "to_uri": 1, "line_number": 1, "status": 1},
            ).limit(100)

            edges = [
                {
                    "from_uri": doc.get("from_uri", ""),
                    "to_uri": doc.get("to_uri", ""),
                    "line_number": doc.get("line_number", 0),
                    "status": doc.get("status", ""),
                }
                for doc in cursor
            ]

            client.close()

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
