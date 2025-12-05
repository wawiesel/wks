"""Monitor status API function.

This function provides filesystem monitoring status and configuration.
Matches CLI: wksc monitor status, MCP: wksm_monitor_status
"""

from ..base import StageResult
from ._validator import _validator
from ...db_helpers import connect_to_mongo, parse_database_key


def cmd_status() -> StageResult:
    """Get filesystem monitoring status and configuration."""
    from ...config import WKSConfig

    config = WKSConfig.load()
    monitor_cfg = config.monitor

    # Count tracked files via DB helpers
    total_files = 0
    try:
        mongo_uri = config.mongo.uri  # type: ignore[attr-defined]
        db_name, coll_name = parse_database_key(monitor_cfg.database)
        client = connect_to_mongo(mongo_uri)
        collection = client[db_name][coll_name]
        total_files = collection.count_documents({})
    except Exception:
        total_files = 0
    finally:
        try:
            client.close()  # type: ignore[name-defined]
        except Exception:
            pass

    # Validate config
    validation = _validator(monitor_cfg)
    result = validation.model_dump()
    result["tracked_files"] = total_files

    has_issues = bool(result.get("issues"))
    result["success"] = not has_issues
    result_msg = (
        f"Monitor status retrieved ({len(result.get('issues', []))} issue(s) found)"
        if has_issues
        else "Monitor status retrieved"
    )

    return StageResult(
        announce="Checking monitor status...",
        result=result_msg,
        output=result,
    )
