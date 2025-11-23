"""WKS CLI - Database commands

Per SPEC.md, database commands are organized by layer:
- wks0 db monitor    -- Query filesystem monitoring database
- wks0 db vault      -- Query knowledge graph links
- wks0 db transform  -- Query transform cache metadata
- wks0 db related    -- Query similarity embeddings (future)
- wks0 db index      -- Query search indices (future)
"""

import argparse
import json
from typing import Optional

from .config import load_config
from .db_helpers import (
    get_monitor_db_config,
    get_transform_db_config,
    get_vault_db_config,
    connect_to_mongo,
)


_LAST_FIELDS = ("last_updated", "last_seen", "timestamp", "last_scan_started_at")


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


def _parse_query_args(args: argparse.Namespace, display) -> tuple[Optional[dict], Optional[dict], Optional[int]]:
    """Parse filter and projection arguments."""
    filter_dict, error = _parse_json_arg(args.filter if hasattr(args, 'filter') else None, "filter", display)
    if error:
        return None, None, error

    projection, error = _parse_json_arg(args.projection if hasattr(args, 'projection') else None, "projection", display)
    if error:
        return None, None, error

    return filter_dict or {}, projection or {}, None


def _build_query_cursor(coll, filter_dict: dict, projection: dict, limit: int, sort_arg: Optional[str]):
    """Build MongoDB query cursor with filter, projection, limit, and sort."""
    cursor = coll.find(filter_dict, projection).limit(limit)

    if sort_arg:
        field, direction = sort_arg.split(':') if ':' in sort_arg else (sort_arg, 'desc')
        sort_dir = 1 if direction.lower().startswith('asc') else -1
        cursor = cursor.sort(field, sort_dir)
    else:
        cursor = cursor.sort("timestamp", -1)

    return cursor


def _clean_document(doc: dict) -> dict:
    """Clean document for display by removing internal fields and formatting."""
    exclude_fields = {"_id", "touches", "avg_time_between_modifications", "touches_per_second"}
    doc_clean = {k: v for k, v in doc.items() if k not in exclude_fields}

    tpd = doc_clean.get("touches_per_day")
    if isinstance(tpd, (int, float)):
        doc_clean["touches_per_day"] = f"{tpd:.2e}"

    return doc_clean


def _display_query_results(display, db_name: str, coll_name: str, total: int, docs: list):
    """Display query results."""
    display.info(f"Database: {db_name}.{coll_name}")
    display.info(f"Total documents: {total}")
    display.info(f"Showing: {len(docs)} documents\n")

    if docs:
        for idx, doc in enumerate(docs, 1):
            doc_clean = _clean_document(doc)
            display.info(f"[{idx}]")
            display.json_output(doc_clean)
            display.info("")
    else:
        display.warning("No documents found")


def _query_collection(uri: str, db_name: str, coll_name: str, args: argparse.Namespace) -> int:
    display = args.display_obj
    filter_dict, projection, error = _parse_query_args(args, display)
    if error:
        return error

    try:
        client = connect_to_mongo(uri)
    except Exception as e:
        display.error(f"Database connection failed: {e}")
        return 2

    try:
        coll = client[db_name][coll_name]
        total = coll.count_documents(filter_dict)
        limit = getattr(args, 'limit', 10)
        sort_arg = getattr(args, 'sort', None) if hasattr(args, 'sort') else None

        cursor = _build_query_cursor(coll, filter_dict, projection, limit, sort_arg)
        docs = list(cursor)
        _display_query_results(display, db_name, coll_name, total, docs)
        return 0
    except Exception as e:
        display.error(f"Query failed: {e}")
        return 1
    finally:
        client.close()


def _db_monitor(args: argparse.Namespace) -> int:
    """Query the filesystem monitoring database."""
    cfg = load_config()
    uri, db_name, coll_name = get_monitor_db_config(cfg)
    return _query_collection(uri, db_name, coll_name, args)


def _db_vault(args: argparse.Namespace) -> int:
    """Query the vault links database."""
    cfg = load_config()
    uri, db_name, coll_name = get_vault_db_config(cfg)
    return _query_collection(uri, db_name, coll_name, args)


def _db_transform(args: argparse.Namespace) -> int:
    """Query the transform cache database."""
    cfg = load_config()
    uri, db_name, coll_name = get_transform_db_config(cfg)
    return _query_collection(uri, db_name, coll_name, args)


def _fetch_last_timestamp(coll) -> str:
    """Return the most recent timestamp-like field from a collection."""
    doc = coll.find_one({}, sort=[("$natural", -1)])
    if not doc:
        return "-"
    for field in _LAST_FIELDS:
        value = doc.get(field)
        if value:
            return value
    return "-"


def _db_status(args: argparse.Namespace) -> int:
    """Show basic statistics for configured databases."""
    cfg = load_config()
    display = args.display_obj
    scopes = []
    for scope, getter in (("monitor", get_monitor_db_config), ("vault", get_vault_db_config)):
        try:
            uri, db_name, coll_name = getter(cfg)
        except Exception as exc:
            display.warning(f"{scope} database unavailable: {exc}")
            continue
        try:
            client = connect_to_mongo(uri)
        except Exception as exc:
            display.error(f"{scope} database connection failed: {exc}")
            return 2
        try:
            coll = client[db_name][coll_name]
            total = coll.count_documents({})
            last_ts = _fetch_last_timestamp(coll)
            scopes.append(
                {
                    "Scope": scope,
                    "Database": f"{db_name}.{coll_name}",
                    "Documents": str(total),
                    "Last Updated": last_ts,
                }
            )
        except Exception as exc:
            display.error(f"{scope} database query failed: {exc}")
            return 1
        finally:
            client.close()

    if not scopes:
        display.warning("No databases configured")
        return 1

    display.table(scopes, headers=["Scope", "Database", "Documents", "Last Updated"], title="Database Status")
    return 0


def setup_db_parser(subparsers) -> argparse.ArgumentParser:
    """Setup argument parser for database commands."""
    dbp = subparsers.add_parser("db", help="Database helpers: query and stats")
    dbsub = dbp.add_subparsers(dest="db_cmd", required=False)

    # wks0 db monitor
    def _add_query_args(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--filter", help='JSON filter, e.g. {"priority": {"$gte": 100}}')
        parser.add_argument("--projection", help='JSON projection, e.g. {"path":1,"priority":1}')
        parser.add_argument("--limit", type=int, default=10, help="Limit results (default: 10)")
        parser.add_argument("--sort", help='Sort field:direction, e.g. "priority:desc" or "timestamp:asc"')

    mon = dbsub.add_parser("monitor", help="Query filesystem monitoring database")
    _add_query_args(mon)
    mon.set_defaults(func=_db_monitor)

    vault = dbsub.add_parser("vault", help="Query Obsidian vault link database")
    _add_query_args(vault)
    vault.set_defaults(func=_db_vault)

    transform = dbsub.add_parser("transform", help="Query transform cache database")
    _add_query_args(transform)
    transform.set_defaults(func=_db_transform)

    status = dbsub.add_parser("status", help="Show configured database statistics")
    status.set_defaults(func=_db_status)

    return dbp
