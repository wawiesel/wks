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

    # Check for old similarity vs new related
    if has_similarity and "related" not in config:
        return True

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
        "exclude_paths": old_monitor.get("exclude_paths", ["~/Library", "~/obsidian", "~/.wks"]),
        "ignore_dirnames": old_monitor.get("ignore_dirnames", [
            ".cache", ".venv", "__pycache__", "_build",
            "build", "dist", "node_modules", "venv"
        ]),
        "ignore_globs": old_monitor.get("ignore_globs", [
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
        "database": "wks_monitor",
        "collection": "filesystem",
        "log_file": "~/.wks/monitor.log"
    }

    # === Vault section (from old obsidian section) ===
    old_obsidian = old_config.get("obsidian", {})
    vault_path = old_config.get("vault_path", "~/obsidian")

    new_config["vault"] = {
        "type": "obsidian",
        "base_dir": vault_path,
        "wks_dir": old_obsidian.get("base_dir", "WKS"),
        "health_file": "WKS/Health.md",
        "activity_file": "WKS/Activity.md",
        "file_ops_file": "WKS/FileOperations.md",
        "extractions_dir": "WKS/Extractions",
        "max_extraction_docs": old_obsidian.get("docs_keep", 50),
        "activity_max_rows": old_obsidian.get("active_files_max_rows", 100),
        "update_frequency_seconds": 10,
        "database": "wks_vault",
        "collection": "links"
    }

    # === DB section ===
    old_mongo = old_config.get("mongo", {})

    new_config["db"] = {
        "uri": old_mongo.get("uri", "mongodb://localhost:27017/"),
        "compatibility": {
            "monitor": "v1",
            "vault": "v1",
            # Keep old compat tags if they exist
            "space": old_mongo.get("compatibility", {}).get("space", "space-v1"),
            "time": old_mongo.get("compatibility", {}).get("time", "time-v1")
        }
    }

    # === Extract section ===
    old_extract = old_config.get("extract", {})
    old_engine = old_extract.get("engine", "docling")

    new_config["extract"] = {
        "output_dir_rules": {
            "resolve_symlinks": True,
            "git_parent": True,
            "underscore_sibling": True
        },
        "engines": {
            "docling": {
                "enabled": old_engine == "docling",
                "is_default": old_engine == "docling",
                "ocr": old_extract.get("ocr", False),
                "timeout_secs": old_extract.get("timeout_secs", 30),
                "write_extension": old_extract.get("write_extension", "md")
            },
            "builtin": {
                "enabled": True,
                "max_chars": 200000
            }
        },
        "_router": {
            "rules": [
                {"extensions": [".pdf", ".docx", ".pptx"], "engine": "docling"},
                {"extensions": [".txt", ".md", ".py"], "engine": "builtin"}
            ],
            "fallback": "builtin"
        }
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

    # === Related section (from old similarity) ===
    old_similarity = old_config.get("similarity", {})

    new_config["related"] = {
        "engines": {
            "embedding": {
                "enabled": old_similarity.get("enabled", True),
                "is_default": True,
                "model": old_similarity.get("model", "all-MiniLM-L6-v2"),
                "min_chars": old_similarity.get("min_chars", 10),
                "max_chars": old_similarity.get("max_chars", 200000),
                "chunk_chars": old_similarity.get("chunk_chars", 1500),
                "chunk_overlap": old_similarity.get("chunk_overlap", 200),
                "offline": old_similarity.get("offline", True),
                # Use old mongo settings if they exist
                "database": old_similarity.get("database",
                           old_mongo.get("space_database", "wks_similarity")),
                "collection": old_similarity.get("collection",
                              old_mongo.get("space_collection", "file_embeddings"))
            },
            "diff_based": {
                "enabled": False,
                "threshold": 0.7,
                "database": "wks_similarity",
                "collection": "diff_similarity"
            }
        },
        "_router": {
            "default": "embedding",
            "rules": [
                {"priority_min": 50, "engine": "embedding"}
            ]
        }
    }

    # === Index section ===
    new_config["index"] = {
        "indices": {
            "main": {
                "enabled": True,
                "type": "embedding",
                "include_extensions": old_similarity.get("include_extensions", [
                    ".md", ".txt", ".py", ".ipynb", ".tex",
                    ".docx", ".pptx", ".pdf", ".html",
                    ".csv", ".xlsx"
                ]),
                "respect_monitor_ignores": old_similarity.get("respect_monitor_ignores", False),
                "respect_priority": True,
                "database": old_mongo.get("space_database", "wks_index_main"),
                "collection": old_mongo.get("space_collection", "documents")
            },
            "code": {
                "enabled": False,
                "type": "ast",
                "include_extensions": [".py", ".js", ".ts", ".cpp"],
                "database": "wks_index_code",
                "collection": "code_blocks"
            }
        }
    }

    # === Search section (new) ===
    new_config["search"] = {
        "default_index": "main",
        "combine": {
            "enabled": False,
            "indices": ["main", "code"],
            "weights": {
                "main": 0.7,
                "code": 0.3
            }
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
