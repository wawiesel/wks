"""Link show API command.

CLI: wksc link show <uri> [--direction to|from|both]
MCP: wksm_link_show
"""

from collections.abc import Iterator
from typing import Any

from wks.api.link.Direction import Direction

from ..config.StageResult import StageResult
from ..config.URI import URI
from ..database.Database import Database


def cmd_show(uri: URI, direction: Direction = Direction.FROM) -> StageResult:
    """Show edges connected to a specific URI.

    Args:
        uri: The candidate URI to search for.
        direction: Direction.TO, Direction.FROM, or Direction.BOTH.
    """
    # Ensure strict type at runtime
    if not isinstance(uri, URI):
        try:
            uri = URI(uri)
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid input: {e}") from e

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        from ..config.WKSConfig import WKSConfig

        yield (0.1, "Loading configuration...")
        config: Any = WKSConfig.load()
        database_name = "edges"

        yield (0.3, f"Searching for links {direction} {uri}...")

        query: dict[str, Any] = {}
        uri_str = str(uri)
        if direction == Direction.FROM:
            query = {"from_local_uri": uri_str}
        elif direction == Direction.TO:
            query = {"to_local_uri": uri_str}
        elif direction == Direction.BOTH:
            query = {"$or": [{"from_local_uri": uri_str}, {"to_local_uri": uri_str}]}

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
