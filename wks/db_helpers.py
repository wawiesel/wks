"""Common database helper functions for WKS CLI.

Reduces duplication across monitor and db commands.
"""

from pymongo import MongoClient


def parse_database_key(db_key: str) -> tuple[str, str]:
    """Parse database key like 'wks.monitor' into (database, collection).

    Args:
        db_key: Database key in format "database.collection"

    Returns:
        Tuple of (database_name, collection_name)

    Raises:
        ValueError: If format is not "database.collection"
    """
    if "." not in db_key:
        raise ValueError(
            f"Database key must be in format 'database.collection' "
            f"(found: {db_key!r}, expected: format like 'wks.monitor')"
        )
    parts = db_key.split(".", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(
            f"Database key must be in format 'database.collection' "
            f"(found: {db_key!r}, expected: format like 'wks.monitor' with both parts non-empty)"
        )
    return parts[0], parts[1]


def get_monitor_db_config(cfg: dict) -> tuple[str, str, str]:
    """Extract monitor database configuration.

    Args:
        cfg: Configuration dictionary

    Returns:
        Tuple of (uri, db_name, coll_name)

    Raises:
        ValueError: If database key is missing or not in "database.collection" format
        KeyError: If required config sections are missing
    """
    monitor_config = cfg.get("monitor")
    if not monitor_config:
        raise KeyError(
            "monitor section is required in config "
            "(found: missing, expected: monitor section with database, include_paths, etc.)"
        )

    db_config = cfg.get("db")
    if not db_config:
        raise KeyError("db section is required in config (found: missing, expected: db section with type and uri)")

    uri = db_config.get("uri")
    if not uri:
        raise KeyError("db.uri is required in config (found: missing, expected: MongoDB connection URI string)")

    db_key = monitor_config.get("database")
    if not db_key:
        raise KeyError(
            "monitor.database is required in config "
            "(found: missing, expected: 'database.collection' format, e.g., 'wks.monitor')"
        )

    db_name, coll_name = parse_database_key(db_key)

    return uri, db_name, coll_name


def get_vault_db_config(cfg: dict) -> tuple[str, str, str]:
    """Extract vault database configuration."""
    vault_cfg = cfg.get("vault")
    if not vault_cfg:
        raise KeyError(
            "vault section is required in config (found: missing, expected: vault section with database, wks_dir, etc.)"
        )

    db_config = cfg.get("db")
    if not db_config:
        raise KeyError("db section is required in config (found: missing, expected: db section with type and uri)")

    uri = db_config.get("uri")
    if not uri:
        raise KeyError("db.uri is required in config (found: missing, expected: MongoDB connection URI string)")

    db_key = vault_cfg.get("database")
    if not db_key:
        raise KeyError(
            "vault.database is required in config "
            "(found: missing, expected: 'database.collection' format, e.g., 'wks.vault')"
        )

    db_name, coll_name = parse_database_key(db_key)
    return uri, db_name, coll_name


def get_transform_db_config(cfg: dict) -> tuple[str, str, str]:
    """Extract transform database configuration."""
    db_config = cfg.get("db")
    if not db_config:
        raise KeyError("db section is required in config (found: missing, expected: db section with type and uri)")

    uri = db_config.get("uri")
    if not uri:
        raise KeyError("db.uri is required in config (found: missing, expected: MongoDB connection URI string)")

    # Transform always uses wks.transform collection
    return uri, "wks", "transform"


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
