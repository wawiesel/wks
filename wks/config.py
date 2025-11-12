from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from .constants import WKS_HOME_EXT
from .utils import wks_home_path, get_wks_home

DEFAULT_MONGO_URI = "mongodb://localhost:27017/"
DEFAULT_SPACE_DATABASE = "wks_similarity"
DEFAULT_SPACE_COLLECTION = "file_embeddings"
DEFAULT_TIME_COLLECTION = "file_snapshots"
DEFAULT_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


def mongo_settings(cfg: Dict[str, Any]) -> Dict[str, str]:
    """Normalize Mongo connection settings from config."""
    sim = cfg.get("similarity") or {}
    mongo = cfg.get("mongo") or {}

    def _norm(value, default):
        if value is None or value == "":
            return default
        return str(value)

    uri = _norm(mongo.get("uri") or sim.get("mongo_uri"), DEFAULT_MONGO_URI)
    space_db = _norm(mongo.get("space_database") or sim.get("database"), DEFAULT_SPACE_DATABASE)
    space_coll = _norm(mongo.get("space_collection") or sim.get("collection"), DEFAULT_SPACE_COLLECTION)
    time_db = _norm(
        mongo.get("time_database")
        or mongo.get("space_database")
        or sim.get("time_database")
        or sim.get("database"),
        DEFAULT_SPACE_DATABASE,
    )
    time_coll = _norm(
        mongo.get("time_collection") or sim.get("snapshots_collection"),
        DEFAULT_TIME_COLLECTION,
    )
    return {
        "uri": uri,
        "space_database": space_db,
        "space_collection": space_coll,
        "time_database": time_db,
        "time_collection": time_coll,
    }


def apply_similarity_mongo_defaults(sim_cfg: Dict[str, Any], mongo_cfg: Dict[str, str]) -> Dict[str, Any]:
    """Ensure similarity config contains the canonical Mongo keys."""
    sim = dict(sim_cfg)
    sim.setdefault("mongo_uri", mongo_cfg["uri"])
    sim.setdefault("database", mongo_cfg["space_database"])
    sim.setdefault("collection", mongo_cfg["space_collection"])
    sim.setdefault("snapshots_collection", mongo_cfg["time_collection"])
    return sim


def timestamp_format(cfg: Dict[str, Any]) -> str:
    disp = cfg.get("display") or {}
    fmt = disp.get("timestamp_format")
    if isinstance(fmt, str) and fmt.strip():
        return fmt
    return DEFAULT_TIMESTAMP_FORMAT


def get_config_path() -> Path:
    """Get path to WKS config file.

    Calls get_wks_home() to determine WKS home directory (checking WKS_HOME env var),
    then returns path to config.json within that directory.

    Returns:
        Path to config.json file

    Examples:
        >>> # WKS_HOME not set
        >>> get_config_path()
        Path("/Users/user/.wks/config.json")
        >>> # WKS_HOME="/custom/path"
        >>> get_config_path()
        Path("/custom/path/config.json")
    """
    return get_wks_home() / "config.json"


def load_config(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load WKS configuration from JSON file.

    If path is None, calls get_config_path() to determine the default config location
    by checking WKS_HOME environment variable and defaulting to ~/.wks/config.json.

    Args:
        path: Optional explicit path to config file. If None, uses get_config_path().

    Returns:
        Configuration dictionary, or empty dict if file doesn't exist or can't be loaded.

    Examples:
        >>> # Load from default location
        >>> config = load_config()
        >>> # Load from custom location
        >>> config = load_config(Path("/custom/config.json"))
    """
    if path is None:
        path = get_config_path()

    if path.exists():
        try:
            with open(path, "r") as fh:
                return json.load(fh)
        except Exception:
            return {}
    return {}


# Backwards compatibility alias
def load_user_config() -> Dict[str, Any]:
    """DEPRECATED: Use load_config() instead."""
    return load_config()
