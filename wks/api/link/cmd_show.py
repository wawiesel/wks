"""Link show API command.

CLI: wksc link show <uri> [--direction to|from|both]
MCP: wksm_link_show
"""

from collections.abc import Iterator
from typing import Any

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

        yield (0.1, "Loading configuration...")
        config: Any = WKSConfig.load()
        database_name = "edges"

        yield (0.3, f"Searching for links {direction} {uri}...")

        query: dict[str, Any] = {}
        if direction == "from":
            query = {"from_local_uri": uri}
        elif direction == "to":
            query = {"to_local_uri": uri}
        elif direction == "both":
            query = {"$or": [{"from_local_uri": uri}, {"to_local_uri": uri}]}

        with Database(config.database, database_name) as database:
            links = list(database.find(query))

            # Format results
            formatted_links = []
            for link in links:
                formatted_links.append(
                    {
                        "from_local_uri": link.get("from_local_uri"),
                        "from_remote_uri": link.get("from_remote_uri"),
                        "to_local_uri": link.get("to_local_uri"),
                        "to_remote_uri": link.get("to_remote_uri"),
                        "line_number": link.get("line_number"),
                        "column_number": link.get("column_number"),
                    }
                )

            result = {
                "uri": uri,
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
