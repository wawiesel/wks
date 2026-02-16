"""Vault links API command.

CLI: wksc vault links <path> [--direction to|from|both]
MCP: wksm_vault_links
"""

from collections.abc import Iterator
from typing import Any, Literal

from ..config.StageResult import StageResult
from ..config.URI import URI
from ..database.Database import Database
from . import VaultLinksOutput


def cmd_links(uri: URI, direction: Literal["to", "from", "both"] = "both") -> StageResult:
    """Query the edges database for links related to a specific file.

    Unlike cmd_check (which scans live files), this queries the database
    populated by cmd_sync to show existing link relationships. Use this to:
    - Find what files link TO a given note (backlinks)
    - Find what files a note links FROM (outlinks)
    - Explore the link graph around a specific file

    Results are limited to 100 edges per query.

    Args:
        path: File path to query. Resolved to vault:/// URI for database lookup.
        direction: Which links to return:
            - "to": Only links pointing TO this file (backlinks)
            - "from": Only links originating FROM this file (outlinks)
            - "both": All links involving this file (default)

    Returns:
        StageResult with VaultLinksOutput containing matching edges.
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
                path=str(uri),
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
            from wks.api.config.normalize_path import normalize_path

            vault_base = normalize_path(config.vault.base_dir)

            # Convert file:// URIs to vault:/// if path is inside the vault
            if uri.is_vault:
                canonical_uri = uri
            elif uri.is_file:
                file_path = uri.path
                try:
                    rel = file_path.relative_to(vault_base)
                    canonical_uri = URI(f"vault:///{rel}")
                except ValueError:
                    canonical_uri = uri  # Outside vault, will fail is_vault check
            else:
                canonical_uri = uri

            if not canonical_uri.is_vault:
                result_obj.output = VaultLinksOutput(
                    errors=[f"Target is not in the vault: {uri}"],
                    warnings=[],
                    path=str(uri),
                    direction=direction,
                    edges=[],
                    count=0,
                    success=False,
                ).model_dump(mode="python")
                result_obj.result = f"Target is not in the vault: {uri}"
                result_obj.success = False
                return

            yield (0.4, "Querying vault database...")
            with Database(config.database, database_name) as database:
                # Filter for vault domain: links with from_local_uri starting with vault:///
                vault_filter = {"from_local_uri": {"$regex": "^vault:///"}}

                # Build query based on direction
                query: dict[str, Any] = {}
                db_uri_str = str(canonical_uri)
                if direction == "from":
                    query = {**vault_filter, "from_local_uri": db_uri_str}
                elif direction == "to":
                    query = {**vault_filter, "to_local_uri": db_uri_str}
                elif direction == "both":
                    query = {
                        **vault_filter,
                        "$or": [{"from_local_uri": db_uri_str}, {"to_local_uri": db_uri_str}],
                    }

                yield (0.6, "Fetching edges...")
                cursor = database.find(
                    query,
                    {"from_local_uri": 1, "to_local_uri": 1, "line_number": 1},
                )

                edges = [
                    {
                        "from_uri": doc["from_local_uri"],
                        "to_uri": doc["to_local_uri"],
                        "line_number": doc["line_number"],
                    }
                    for doc in list(cursor)[:100]  # Limit to 100
                ]

            yield (1.0, "Complete")
            result_obj.output = VaultLinksOutput(
                errors=[],
                warnings=[],
                path=str(uri),
                direction=direction,
                edges=edges,
                count=len(edges),
                success=True,
            ).model_dump(mode="python")
            result_obj.result = f"Found {len(edges)} edge(s) for {uri}"
            result_obj.success = True

        except Exception as e:
            result_obj.output = VaultLinksOutput(
                errors=[f"Query failed: {e}"],
                warnings=[],
                path=str(uri),
                direction=direction,
                edges=[],
                count=0,
                success=False,
            ).model_dump(mode="python")
            result_obj.result = f"Vault links failed: {e}"
            result_obj.success = False

    return StageResult(
        announce=f"Finding links for {uri}...",
        progress_callback=do_work,
    )
