"""Common database helper functions for WKS CLI.

Reduces duplication across monitor and db commands.
"""

from typing import Dict, Tuple
from pymongo import MongoClient


def get_monitor_db_config(cfg: dict) -> Tuple[str, str, str]:
    """Extract monitor database configuration.

    Args:
        cfg: Configuration dictionary

    Returns:
        Tuple of (uri, db_name, coll_name)
    """
    monitor_config = cfg.get("monitor", {})
    db_config = cfg.get("db", {}) or cfg.get("mongo", {})

    uri = db_config.get("uri", "mongodb://localhost:27017/")
    db_name = monitor_config.get("database", "wks")
    coll_name = monitor_config.get("collection", "monitor")

    return uri, db_name, coll_name


def connect_to_mongo(uri: str, timeout_ms: int = 5000) -> MongoClient:
    """Connect to MongoDB with timeout.

    Args:
        uri: MongoDB connection URI
        timeout_ms: Server selection timeout in milliseconds

    Returns:
        Connected MongoClient

    Raises:
        Exception: If connection fails
    """
    client = MongoClient(uri, serverSelectionTimeoutMS=timeout_ms)
    client.server_info()  # Test connection
    return client
