from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from .constants import WKS_HOME_EXT
from .utils import wks_home_path

DEFAULT_MONGO_URI = "mongodb://localhost:27027/"
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


def load_user_config() -> Dict[str, Any]:
    path = wks_home_path("config.json")
    if path.exists():
        try:
            with open(path, "r") as fh:
                return json.load(fh)
        except Exception:
            return {}
    return {}
