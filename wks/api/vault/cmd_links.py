from collections.abc import Iterator
from typing import Any, Literal

from ..config.StageResult import StageResult
from ..config.URI import URI
from ..database.Database import Database
from . import VaultLinksOutput


def cmd_links(uri: URI, direction: Literal["to", "from", "both"] = "both") -> StageResult:
    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        from ..config.WKSConfig import WKSConfig

        yield (0.1, "Loading configuration...")
        try:
            config: Any = WKSConfig.load()
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

        database_name = "edges"
        yield (0.3, "Resolving vault path...")
        try:
            from wks.api.config.normalize_path import normalize_path

            vault_base = normalize_path(config.vault.base_dir)

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
                vault_filter = {"from_local_uri": {"$regex": "^vault:///"}}

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
