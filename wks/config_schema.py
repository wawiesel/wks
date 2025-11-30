"""Config schema and migration for WKS layered architecture."""

import copy
from pathlib import Path
from typing import Dict, Any, Optional


def is_old_config(config: Dict[str, Any]) -> bool:
    """Detect if config is old format.

    Old format has:
    - 'vault_path' at top level
    - 'obsidian' section (not 'vault')
    - 'similarity' section (not 'related')
    - No 'monitor.managed_directories'

    Args:
        config: Config dict

    Returns:
        True if old format detected
    """
    # Check for old format indicators
    has_vault_path = "vault_path" in config
    has_obsidian = "obsidian" in config
    has_similarity = "similarity" in config
    has_vault = "vault" in config

    # Old format has vault_path and obsidian, not vault
    if has_vault_path and has_obsidian and not has_vault:
        return True

    # Check for new format indicators
    if "monitor" in config:
        monitor = config["monitor"]
        if "managed_directories" in monitor:
            return False  # Definitely new format

    return False


def migrate_config(old_config: Dict[str, Any]) -> Dict[str, Any]:
    """Migrate old config format to new layered architecture format.

    Args:
        old_config: Config in old format

    Returns:
        Config in new format
    """
    new_config = {}

    # === Monitor section ===
    old_monitor = old_config.get("monitor", {})

    new_config["monitor"] = {
        "include_paths": old_monitor.get("include_paths", ["~"]),
        "exclude_paths": old_monitor.get("exclude_paths", ["~/Library", "~/.wks"]),
        "include_dirnames": old_monitor.get("include_dirnames", []),
        "exclude_dirnames": old_monitor.get("ignore_dirnames", [
            ".cache", ".venv", "__pycache__", "_build",
            "build", "dist", "node_modules", "venv"
        ]),
        "include_globs": old_monitor.get("include_globs", []),
        "exclude_globs": old_monitor.get("ignore_globs", [
            "**/.DS_Store", "*.swp", "*.tmp", "*~", "._*", "~$*", ".~lock.*#"
        ]),
        # New: managed directories with priorities
        "managed_directories": {
            "~/Desktop": 150,
            "~/deadlines": 120,
            "~": 100,
            "~/Documents": 100,
            "~/Pictures": 80,
            "~/Downloads": 50,
        },
        # New: priority calculation config
        "priority": {
            "depth_multiplier": 0.9,
            "underscore_divisor": 2,
            "single_underscore_divisor": 64,
            "extension_weights": {
                ".docx": 1.3,
                ".pptx": 1.3,
                ".pdf": 1.1,
                "default": 1.0
            },
            "auto_index_min": 2
        },
        "database": "wks.monitor",
        "max_documents": 1000000,
        "log_file": "~/.wks/monitor.log"
    }

    touch_weight = old_monitor.get("touch_weight")
    if isinstance(touch_weight, (int, float)):
        new_config["monitor"]["touch_weight"] = float(touch_weight)
    else:
        new_config["monitor"]["touch_weight"] = 0.1

    # === Vault section (from old obsidian section) ===
    old_obsidian = old_config.get("obsidian", {})
    vault_path = old_config.get("vault_path")
    if not vault_path:
        raise ValueError("vault_path is required in legacy config (found: missing)")

    new_config["vault"] = {
        "type": "obsidian",
        "base_dir": vault_path,
        "wks_dir": old_obsidian.get("base_dir", "WKS"),
        "update_frequency_seconds": 10,
        "database": "wks.vault"
    }

    # === DB section ===
    old_mongo = old_config.get("mongo", {})

    new_config["db"] = {
        "type": "mongodb",  # Database type: mongodb (only supported type currently)
        "uri": old_mongo.get("uri", "mongodb://localhost:27017/")
    }

    # === Transform section ===
    old_extract = old_config.get("extract", {})
    old_engine = old_extract.get("engine", "docling")

    new_config["transform"] = {
        "cache_location": ".wks/cache"
    }

    # === Diff section (new) ===
    new_config["diff"] = {
        "engines": {
            "bdiff": {
                "enabled": True,
                "is_default": True,
                "algorithm": "bsdiff"
            },
            "text": {
                "enabled": True,
                "algorithm": "unified",
                "context_lines": 3
            }
        },
        "_router": {
            "rules": [
                {"extensions": [".txt", ".md", ".py", ".json"], "engine": "text"},
                {"mime_prefix": "text/", "engine": "text"}
            ],
            "fallback": "bdiff"
        }
    }



    # === Display section ===
    old_display = old_config.get("display", {})

    new_config["display"] = {
        "timestamp_format": old_display.get("timestamp_format", "%Y-%m-%d %H:%M:%S")
    }

    # === Activity section (keep for now) ===
    if "activity" in old_config:
        new_config["activity"] = copy.deepcopy(old_config["activity"])

    # === Metrics section (keep for now) ===
    if "metrics" in old_config:
        new_config["metrics"] = copy.deepcopy(old_config["metrics"])

    return new_config


def validate_config(config: Dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate config structure.

    Args:
        config: Config dict to validate

    Returns:
        Tuple of (is_valid, list_of_error_messages)
    """
    errors = []

    # Check for required top-level sections
    required_sections = ["monitor", "vault", "db"]
    for section in required_sections:
        if section not in config:
            errors.append(f"Missing required section: {section}")

    # Validate monitor section
    if "monitor" in config:
        monitor = config["monitor"]
        if "managed_directories" not in monitor:
            errors.append("monitor section missing 'managed_directories'")
        if "priority" not in monitor:
            errors.append("monitor section missing 'priority'")

    # Validate vault section
    if "vault" in config:
        vault = config["vault"]
        if "base_dir" not in vault:
            errors.append("vault section missing 'base_dir'")
        if "database" not in vault:
            errors.append("vault section missing 'database'")

    # Validate db section
    if "db" in config:
        db = config["db"]
        if "uri" not in db:
            errors.append("db section missing 'uri'")

    return (len(errors) == 0, errors)
