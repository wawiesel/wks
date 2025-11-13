"""Configuration validation for WKS."""

from pathlib import Path
from typing import Any, Dict, List, Tuple


class ConfigValidationError(Exception):
    """Raised when configuration is invalid."""
    pass


def validate_config(cfg: Dict[str, Any]) -> List[str]:
    """
    Validate WKS configuration.

    Returns:
        List of error messages (empty if valid)
    """
    errors = []

    # Vault config (simplified: base_dir, wks_dir, update_frequency_seconds, type, database)
    vault = cfg.get("vault", {})
    if not isinstance(vault, dict):
        errors.append("'vault' must be an object")
    else:
        if "base_dir" not in vault:
            errors.append("vault.base_dir is required")
        elif vault.get("base_dir"):
            vault_path = Path(str(vault["base_dir"])).expanduser()
            if not vault_path.exists():
                errors.append(f"vault.base_dir does not exist: {vault_path}")
            elif not vault_path.is_dir():
                errors.append(f"vault.base_dir is not a directory: {vault_path}")

        if "wks_dir" not in vault:
            errors.append("vault.wks_dir is required")

        if "update_frequency_seconds" not in vault:
            errors.append("vault.update_frequency_seconds is required")
        else:
            try:
                val = int(vault["update_frequency_seconds"])
                if val < 1:
                    errors.append("vault.update_frequency_seconds must be positive")
            except (ValueError, TypeError):
                errors.append("vault.update_frequency_seconds must be an integer")

        if "database" not in vault:
            errors.append("vault.database is required")
        else:
            db_key = vault["database"]
            if not isinstance(db_key, str) or "." not in db_key:
                errors.append("vault.database must be in format 'database.collection'")
            else:
                parts = db_key.split(".", 1)
                if len(parts) != 2 or not parts[0] or not parts[1]:
                    errors.append("vault.database must be in format 'database.collection'")

    # Monitor config
    mon = cfg.get("monitor", {})
    if not isinstance(mon, dict):
        errors.append("'monitor' must be an object")
    else:
        if "database" not in mon:
            errors.append("monitor.database is required")
        else:
            db_key = mon["database"]
            if not isinstance(db_key, str) or "." not in db_key:
                errors.append("monitor.database must be in format 'database.collection'")
            else:
                parts = db_key.split(".", 1)
                if len(parts) != 2 or not parts[0] or not parts[1]:
                    errors.append("monitor.database must be in format 'database.collection'")

        required_mon = ["include_paths", "exclude_paths", "ignore_dirnames",
                        "ignore_globs", "touch_weight"]
        for key in required_mon:
            if key not in mon:
                errors.append(f"monitor.{key} is required")

        # Validate paths exist
        if "include_paths" in mon:
            if not isinstance(mon["include_paths"], list):
                errors.append("monitor.include_paths must be an array")
            else:
                for path_str in mon["include_paths"]:
                    path = Path(str(path_str)).expanduser()
                    if not path.exists():
                        errors.append(f"monitor.include_paths contains non-existent path: {path}")

        try:
            weight_val = float(mon.get("touch_weight"))
        except (TypeError, ValueError):
            errors.append("monitor.touch_weight must be a number between 0.001 and 1")
        else:
            if weight_val < 0.001 or weight_val > 1.0:
                errors.append("monitor.touch_weight must be between 0.001 and 1")

    # Extract config
    ext = cfg.get("extract", {})
    if isinstance(ext, dict):
        if "engine" in ext:
            engine = str(ext["engine"]).lower()
            if engine not in ["docling", "builtin"]:
                errors.append(f"extract.engine must be 'docling' or 'builtin', got: {engine}")

        if "timeout_secs" in ext:
            try:
                val = int(ext["timeout_secs"])
                if val < 1:
                    errors.append("extract.timeout_secs must be positive")
            except (ValueError, TypeError):
                errors.append("extract.timeout_secs must be an integer")

    # DB config
    db = cfg.get("db")
    if not db:
        errors.append("db section is required")
    elif not isinstance(db, dict):
        errors.append("'db' must be an object")
    else:
        db_type = db.get("type")
        if not db_type:
            errors.append("db.type is required")
        elif db_type != "mongodb":
            errors.append("db.type must be 'mongodb' (only supported type)")

        if "uri" not in db:
            errors.append("db.uri is required")
        elif db_type == "mongodb":
            uri = str(db["uri"])
            if not uri.startswith("mongodb://"):
                errors.append("db.uri must start with 'mongodb://' when db.type is 'mongodb'")

    return errors


def validate_and_raise(cfg: Dict[str, Any]) -> None:
    """
    Validate configuration and raise ConfigValidationError if invalid.

    Args:
        cfg: Configuration dictionary

    Raises:
        ConfigValidationError: If configuration is invalid
    """
    errors = validate_config(cfg)
    if errors:
        msg = "Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        raise ConfigValidationError(msg)
