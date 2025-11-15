"""Configuration validation for WKS."""

from pathlib import Path
from typing import Any, Dict, List, Tuple


class ConfigValidationError(Exception):
    """Raised when configuration is invalid."""
    pass


def _validate_database_key(db_key: Any, section: str) -> List[str]:
    """Validate database key format (database.collection)."""
    errors = []
    if not db_key:
        errors.append(f"{section}.database is required (found: {db_key!r}, expected: 'database.collection' format, e.g., 'wks.monitor')")
    elif not isinstance(db_key, str):
        errors.append(f"{section}.database must be a string (found: {type(db_key).__name__} = {db_key!r}, expected: string in 'database.collection' format)")
    elif "." not in db_key:
        errors.append(f"{section}.database must be in format 'database.collection' (found: {db_key!r}, expected: format like 'wks.monitor')")
    else:
        parts = db_key.split(".", 1)
        if len(parts) != 2 or not parts[0] or not parts[1]:
            errors.append(f"{section}.database must be in format 'database.collection' (found: {db_key!r}, expected: format like 'wks.monitor' with both parts non-empty)")
    return errors


def _validate_vault_config(vault: Dict[str, Any]) -> List[str]:
    """Validate vault configuration section."""
    errors = []
    if not isinstance(vault, dict):
        errors.append("'vault' must be an object")
        return errors

    if "base_dir" not in vault:
        errors.append("vault.base_dir is required (found: missing, expected: path to Obsidian vault directory)")
    elif vault.get("base_dir"):
        vault_path = Path(str(vault["base_dir"])).expanduser()
        if not vault_path.exists():
            errors.append(f"vault.base_dir does not exist (found: {vault_path!r}, expected: existing directory path)")
        elif not vault_path.is_dir():
            errors.append(f"vault.base_dir is not a directory (found: {vault_path!r} is a file, expected: directory path)")

    if "wks_dir" not in vault:
        errors.append("vault.wks_dir is required (found: missing, expected: subdirectory name within vault, e.g., 'WKS')")

    if "update_frequency_seconds" not in vault:
        errors.append("vault.update_frequency_seconds is required (found: missing, expected: positive integer)")
    else:
        try:
            val = int(vault["update_frequency_seconds"])
            if val < 1:
                errors.append(f"vault.update_frequency_seconds must be positive (found: {val}, expected: integer >= 1)")
        except (ValueError, TypeError):
            errors.append(f"vault.update_frequency_seconds must be an integer (found: {type(vault['update_frequency_seconds']).__name__} = {vault['update_frequency_seconds']!r}, expected: integer)")

    if "database" in vault:
        errors.extend(_validate_database_key(vault["database"], "vault"))

    return errors


def _validate_monitor_config(mon: Dict[str, Any]) -> List[str]:
    """Validate monitor configuration section."""
    errors = []
    if not isinstance(mon, dict):
        errors.append("'monitor' must be an object")
        return errors

    if "database" in mon:
        errors.extend(_validate_database_key(mon["database"], "monitor"))

    required_mon = ["include_paths", "exclude_paths", "ignore_dirnames", "ignore_globs", "touch_weight"]
    for key in required_mon:
        if key not in mon:
            errors.append(f"monitor.{key} is required")

    if "include_paths" in mon:
        if not isinstance(mon["include_paths"], list):
            errors.append(f"monitor.include_paths must be an array (found: {type(mon['include_paths']).__name__} = {mon['include_paths']!r}, expected: list of path strings)")
        else:
            for idx, path_str in enumerate(mon["include_paths"]):
                path = Path(str(path_str)).expanduser()
                if not path.exists():
                    errors.append(f"monitor.include_paths[{idx}] does not exist (found: {path!r}, expected: existing directory path)")

    if "touch_weight" in mon:
        try:
            weight_val = float(mon.get("touch_weight"))
        except (TypeError, ValueError):
            errors.append(
                f"monitor.touch_weight must be a number between 0.001 and 1 (found: {
                    type(
                        mon.get('touch_weight')).__name__} = {
                    mon.get('touch_weight')!r}, expected: float between 0.001 and 1.0)")
        else:
            if weight_val < 0.001 or weight_val > 1.0:
                errors.append(f"monitor.touch_weight must be between 0.001 and 1 (found: {weight_val}, expected: 0.001 <= value <= 1.0)")

    if "dot_whitelist" in mon and not isinstance(mon["dot_whitelist"], list):
        errors.append(f"monitor.dot_whitelist must be an array when provided (found: {type(mon['dot_whitelist']).__name__} = {mon['dot_whitelist']!r}, expected: list of directory names)")

    return errors


def _validate_extract_config(ext: Dict[str, Any]) -> List[str]:
    """Validate extract configuration section."""
    errors = []
    if not isinstance(ext, dict):
        return errors

    if "engine" in ext:
        engine = str(ext["engine"]).lower()
        if engine not in ["docling", "builtin"]:
            errors.append(f"extract.engine must be 'docling' or 'builtin' (found: {ext['engine']!r}, expected: 'docling' or 'builtin')")

    if "timeout_secs" in ext:
        try:
            val = int(ext["timeout_secs"])
            if val < 1:
                errors.append(f"extract.timeout_secs must be positive (found: {val}, expected: integer >= 1)")
        except (ValueError, TypeError):
            errors.append(f"extract.timeout_secs must be an integer (found: {type(ext['timeout_secs']).__name__} = {ext['timeout_secs']!r}, expected: integer)")

    return errors


def _validate_db_config(db: Dict[str, Any]) -> List[str]:
    """Validate db configuration section."""
    errors = []
    if not db:
        errors.append("db section is required")
        return errors

    if not isinstance(db, dict):
        errors.append("'db' must be an object")
        return errors

    db_type = db.get("type")
    if not db_type:
        errors.append("db.type is required (found: missing, expected: 'mongodb')")
    elif db_type != "mongodb":
        errors.append(f"db.type must be 'mongodb' (found: {db_type!r}, expected: 'mongodb' - only supported type)")

    if "uri" not in db:
        errors.append("db.uri is required (found: missing, expected: MongoDB connection URI)")
    elif db_type == "mongodb":
        uri = str(db["uri"])
        if not uri.startswith("mongodb://"):
            errors.append(f"db.uri must start with 'mongodb://' when db.type is 'mongodb' (found: {uri[:20]}..., expected: URI starting with 'mongodb://')")

    return errors


def validate_config(cfg: Dict[str, Any]) -> List[str]:
    """
    Validate WKS configuration.

    Returns:
        List of error messages (empty if valid)
    """
    errors = []
    errors.extend(_validate_vault_config(cfg.get("vault", {})))
    errors.extend(_validate_monitor_config(cfg.get("monitor", {})))
    errors.extend(_validate_extract_config(cfg.get("extract", {})))
    errors.extend(_validate_db_config(cfg.get("db")))
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
