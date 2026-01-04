"""Link show API command.

CLI: wksc link show <uri> [--direction to|from|both]
MCP: wksm_link_show
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from wks.utils.path_to_uri import path_to_uri

from ..database.Database import Database
from ..StageResult import StageResult


def cmd_show(uri: str, direction: str = "from") -> StageResult:
    """Show edges connected to a specific URI.

    Args:
        uri: The candidate URI to search for.
        direction: 'to', 'from', or 'both'.
    """

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        from ..config.WKSConfig import WKSConfig

        # Resolve URI if it looks like a local file path
        search_uri = uri
        if "://" not in uri:
            try:
                p = Path(uri).resolve()
                if p.exists():
                    search_uri = path_to_uri(p)
            except Exception:
                pass

        yield (0.1, "Loading configuration...")
        config: Any = WKSConfig.load()
        database_name = "edges"

        yield (0.3, f"Searching for links {direction} {search_uri}...")

        query: dict[str, Any] = {}
        if direction == "from":
            query = {"from_local_uri": search_uri}
        elif direction == "to":
            query = {"to_local_uri": search_uri}
        elif direction == "both":
            query = {"$or": [{"from_local_uri": search_uri}, {"to_local_uri": search_uri}]}

        with Database(config.database, database_name) as database:
            links = list(database.find(query))

            # Format results
            formatted_links = []
            for link in links:
                formatted_links.append(
                    {
                        "from_local_uri": link["from_local_uri"],
                        "from_remote_uri": link["from_remote_uri"],
                        "to_local_uri": link["to_local_uri"],
                        "to_remote_uri": link["to_remote_uri"],
                        "line_number": link["line_number"],
                        "column_number": link["column_number"],
                    }
                )

            result = {
                "uri": search_uri,
                "direction": direction,
                "links": formatted_links,
            }

            yield (1.0, "Complete")
            result_obj.output = result
            result_obj.result = f"Found {len(formatted_links)} links"
            result_obj.success = True

    return StageResult(
        announce=f"Showing links for {uri}...",
        progress_callback=do_work,
    )
