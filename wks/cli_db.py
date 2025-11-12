"""WKS CLI - Database commands

Per SPEC.md, database commands are organized by layer:
- wkso db monitor    -- Query filesystem monitoring database
- wkso db vault      -- Query knowledge graph links (future)
- wkso db related    -- Query similarity embeddings (future)
- wkso db index      -- Query search indices (future)
"""

import argparse
import json
from typing import Optional

from .config import load_config
from .db_helpers import get_monitor_db_config, connect_to_mongo


def _parse_json_arg(value: Optional[str], arg_name: str, display) -> tuple[Optional[dict], Optional[int]]:
    """Parse a JSON argument string.

    Returns:
        Tuple of (parsed_dict, error_code). If successful, error_code is None.
    """
    if not value:
        return {}, None

    try:
        return json.loads(value), None
    except json.JSONDecodeError as e:
        display.error(f"Invalid JSON {arg_name}: {e}")
        return None, 2


def _db_monitor(args: argparse.Namespace) -> int:
    """Query the filesystem monitoring database."""
    display = args.display_obj
    cfg = load_config()

    # Get database configuration
    uri, db_name, coll_name = get_monitor_db_config(cfg)

    # Parse filter
    filter_dict, error = _parse_json_arg(args.filter if hasattr(args, 'filter') else None,
                                          "filter", display)
    if error:
        return error

    # Parse projection
    projection, error = _parse_json_arg(args.projection if hasattr(args, 'projection') else None,
                                        "projection", display)
    if error:
        return error

    # Connect to database
    try:
        client = connect_to_mongo(uri)
    except Exception as e:
        display.error(f"Database connection failed: {e}")
        return 2

    try:
        coll = client[db_name][coll_name]

        # Get count
        total = coll.count_documents(filter_dict)

        # Query with limit
        limit = getattr(args, 'limit', 10)
        cursor = coll.find(filter_dict, projection).limit(limit)

        # Sort if specified
        if hasattr(args, 'sort') and args.sort:
            field, direction = args.sort.split(':') if ':' in args.sort else (args.sort, 'desc')
            sort_dir = 1 if direction.lower().startswith('asc') else -1
            cursor = cursor.sort(field, sort_dir)
        else:
            # Default: sort by timestamp descending
            cursor = cursor.sort("timestamp", -1)

        docs = list(cursor)

        # Display results
        display.info(f"Database: {db_name}.{coll_name}")
        display.info(f"Total documents: {total}")
        display.info(f"Showing: {len(docs)} documents\n")

        if docs:
            for idx, doc in enumerate(docs, 1):
                # Remove MongoDB _id for cleaner display
                doc_clean = {k: v for k, v in doc.items() if k != '_id'}
                display.info(f"[{idx}]")
                display.json_output(doc_clean)
                display.info("")  # Blank line between docs
        else:
            display.warning("No documents found")

        return 0

    except Exception as e:
        display.error(f"Query failed: {e}")
        return 1
    finally:
        client.close()


def setup_db_parser(subparsers) -> argparse.ArgumentParser:
    """Setup argument parser for database commands."""
    dbp = subparsers.add_parser("db", help="Database helpers: query and stats")
    dbsub = dbp.add_subparsers(dest="db_cmd", required=False)

    # wkso db monitor
    mon = dbsub.add_parser("monitor", help="Query filesystem monitoring database")
    mon.add_argument("--filter", help='JSON filter, e.g. {"priority": {"$gte": 100}}')
    mon.add_argument("--projection", help='JSON projection, e.g. {"path":1,"priority":1}')
    mon.add_argument("--limit", type=int, default=10, help="Limit results (default: 10)")
    mon.add_argument("--sort", help='Sort field:direction, e.g. "priority:desc" or "timestamp:asc"')
    mon.set_defaults(func=_db_monitor)

    return dbp
