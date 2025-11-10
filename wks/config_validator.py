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

    # Required top-level keys
    if "vault_path" not in cfg or not str(cfg.get("vault_path", "")).strip():
        errors.append("'vault_path' is required and must be non-empty")

    # Validate vault_path exists if provided
    if "vault_path" in cfg:
        vault_path = Path(str(cfg["vault_path"])).expanduser()
        if not vault_path.exists():
            errors.append(f"vault_path does not exist: {vault_path}")
        elif not vault_path.is_dir():
            errors.append(f"vault_path is not a directory: {vault_path}")

    # Obsidian config
    obs = cfg.get("obsidian", {})
    if not isinstance(obs, dict):
        errors.append("'obsidian' must be an object")
    else:
        required_obs = ["base_dir", "log_max_entries", "active_files_max_rows",
                       "source_max_chars", "destination_max_chars"]
        for key in required_obs:
            if key not in obs:
                errors.append(f"obsidian.{key} is required")

        # Validate numeric values
        if "log_max_entries" in obs:
            try:
                val = int(obs["log_max_entries"])
                if val < 1:
                    errors.append("obsidian.log_max_entries must be positive")
            except (ValueError, TypeError):
                errors.append("obsidian.log_max_entries must be an integer")

        if "active_files_max_rows" in obs:
            try:
                val = int(obs["active_files_max_rows"])
                if val < 1:
                    errors.append("obsidian.active_files_max_rows must be positive")
            except (ValueError, TypeError):
                errors.append("obsidian.active_files_max_rows must be an integer")

    # Monitor config
    mon = cfg.get("monitor", {})
    if not isinstance(mon, dict):
        errors.append("'monitor' must be an object")
    else:
        required_mon = ["include_paths", "exclude_paths", "ignore_dirnames",
                       "ignore_globs", "state_file"]
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

    # Similarity config (if enabled)
    sim = cfg.get("similarity", {})
    if isinstance(sim, dict) and sim.get("enabled"):
        if "model" not in sim:
            errors.append("similarity.model is required when similarity is enabled")
        if "include_extensions" not in sim:
            errors.append("similarity.include_extensions is required when similarity is enabled")

        # Validate min/max chars
        if "min_chars" in sim:
            try:
                val = int(sim["min_chars"])
                if val < 0:
                    errors.append("similarity.min_chars must be non-negative")
            except (ValueError, TypeError):
                errors.append("similarity.min_chars must be an integer")

        if "max_chars" in sim:
            try:
                val = int(sim["max_chars"])
                if val < 1:
                    errors.append("similarity.max_chars must be positive")
            except (ValueError, TypeError):
                errors.append("similarity.max_chars must be an integer")

        # Validate min < max
        if "min_chars" in sim and "max_chars" in sim:
            try:
                if int(sim["min_chars"]) >= int(sim["max_chars"]):
                    errors.append("similarity.min_chars must be less than max_chars")
            except (ValueError, TypeError):
                pass  # Already reported above

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

    # Mongo config
    mongo = cfg.get("mongo", {})
    if isinstance(mongo, dict):
        if "uri" in mongo:
            uri = str(mongo["uri"])
            if not uri.startswith("mongodb://"):
                errors.append("mongo.uri must start with 'mongodb://'")

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
