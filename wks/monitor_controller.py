"""
Monitor Controller - Business logic for filesystem monitoring operations.

This module contains all monitor-related business logic, completely separated
from the CLI display layer. This enables:
- Easy unit testing
- Reuse by MCP server
- Zero code duplication per SPEC.md
"""

import logging
from dataclasses import dataclass, field, asdict, fields
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Set, Iterable
import fnmatch
import math

from .constants import WKS_DOT_DIRS
from .monitor_rules import MonitorRules

logger = logging.getLogger(__name__)


def _canonicalize_path(path_str: str) -> str:
    """Normalize a path string for comparison."""
    path_obj = Path(path_str).expanduser()
    try:
        return str(path_obj.resolve(strict=False))
    except Exception:
        return str(path_obj)


def _build_canonical_map(values: List[str]) -> Dict[str, List[str]]:
    """Map canonical path strings to the original representations."""
    mapping: Dict[str, List[str]] = {}
    for raw in values:
        canonical = _canonicalize_path(raw)
        mapping.setdefault(canonical, []).append(raw)
    return mapping


def _find_matching_path_key(path_map: Dict[str, Any], candidate: str) -> Optional[str]:
    """Find the key in a path map that canonically matches candidate."""
    candidate_norm = _canonicalize_path(candidate)
    for key in path_map.keys():
        if _canonicalize_path(key) == candidate_norm:
            return key
    return None


class ValidationError(Exception):
    """Exception that collects multiple validation errors."""

    def __init__(self, errors: List[str]):
        self.errors = errors
        message = "Validation failed with multiple errors:\n" + "\n".join(f"  - {e}" for e in errors)
        super().__init__(message)


class MonitorValidator:
    """Validation logic for monitor configuration."""

    @staticmethod
    def status_symbol(error_msg: Optional[str], is_valid: bool = True) -> str:
        """Convert validation result to colored status symbol."""
        return "[green]✓[/]" if not error_msg else "[yellow]⚠[/]" if is_valid else "[red]✗[/]"

    @staticmethod
    def validate_dirname_entry(dirname: str) -> Tuple[bool, Optional[str]]:
        """Validate include/exclude dirname entries."""
        if not dirname or not dirname.strip():
            return False, "Directory name cannot be empty"
        if any(ch in dirname for ch in "*?[]"):
            return False, "Directory names cannot contain wildcard characters (*, ?, [)"
        return True, None

    @staticmethod
    def dirname_redundancy(dirname: str, related_globs: List[str], relation: str) -> Optional[str]:
        """Detect redundant dirname entries already covered by globs."""
        normalized = dirname.strip()
        for pattern in related_globs:
            pattern = pattern.strip()
            if not pattern:
                continue
            simplified = pattern.rstrip("/")
            simplified = simplified.removeprefix("**/").removesuffix("/**")
            if simplified == normalized and not any(ch in pattern for ch in "*?[]"):
                return f"Redundant: dirname '{dirname}' already covered by {relation} glob '{pattern}'"
        return None

    @staticmethod
    def validate_glob_pattern(pattern: str) -> Tuple[bool, Optional[str]]:
        """Validate glob syntax for include/exclude lists."""
        if not pattern or not pattern.strip():
            return False, "Glob pattern cannot be empty"
        try:
            fnmatch.fnmatch("test", pattern)
            return True, None
        except Exception as e:
            return False, f"Invalid glob syntax: {str(e)}"

    @staticmethod
    def validate_managed_directory(managed_path: str, rules: MonitorRules) -> Tuple[bool, Optional[str]]:
        """Validate that a managed_directory would actually be monitored."""
        managed_resolved = Path(managed_path).expanduser().resolve()

        wks_home = Path("~/.wks").expanduser().resolve()
        if managed_resolved == wks_home or str(managed_resolved).startswith(str(wks_home) + "/"):
            return False, "In WKS home directory (automatically ignored)"

        if ".wkso" in managed_resolved.parts:
            return False, "Contains .wkso directory (automatically ignored)"

        allowed, trace = rules.explain(managed_resolved)
        if allowed:
            return True, None

        if trace:
            return False, trace[-1]
        return False, "Excluded by monitor rules"


@dataclass
class ListOperationResult:
    """Result of adding/removing items from a monitor list."""
    success: bool
    message: str
    value_stored: Optional[str] = None
    value_removed: Optional[str] = None
    not_found: bool = False
    already_exists: bool = False
    validation_failed: bool = False

    def __post_init__(self):
        """Validate after initialization."""
        if not self.message:
            raise ValueError(f"ListOperationResult.message cannot be empty (found: {self.message!r}, expected: non-empty string)")
        if self.success and self.not_found:
            raise ValueError(
                f"ListOperationResult: success cannot be True when not_found is True (found: success={self.success}, not_found={self.not_found}, expected: success=False when not_found=True)"
            )
        if self.success and self.already_exists:
            raise ValueError(
                f"ListOperationResult: success cannot be True when already_exists is True (found: success={self.success}, already_exists={self.already_exists}, expected: success=False when already_exists=True)"
            )
        if self.success and self.validation_failed:
            raise ValueError(
                f"ListOperationResult: success cannot be True when validation_failed is True (found: success={self.success}, validation_failed={self.validation_failed}, expected: success=False when validation_failed=True)"
            )


@dataclass
class ManagedDirectoryInfo:
    """Information about a managed directory."""
    priority: int
    valid: bool
    error: Optional[str] = None

    def __post_init__(self):
        """Validate after initialization."""
        if self.priority < 0:
            raise ValueError(f"ManagedDirectoryInfo.priority must be non-negative (found: {self.priority}, expected: integer >= 0)")


@dataclass
class ManagedDirectoriesResult:
    """Result of get_managed_directories()."""
    managed_directories: Dict[str, int]
    count: int
    validation: Dict[str, ManagedDirectoryInfo]


@dataclass
class MonitorConfig:
    """Monitor configuration loaded from config dict with validation."""
    include_paths: List[str]
    exclude_paths: List[str]
    include_dirnames: List[str]
    exclude_dirnames: List[str]
    include_globs: List[str]
    exclude_globs: List[str]
    database: str
    managed_directories: Dict[str, int]
    touch_weight: float = 0.1
    priority: Dict[str, Any] = field(default_factory=dict)
    max_documents: int = 1000000
    prune_interval_secs: float = 300.0

    def __post_init__(self):
        """Validate monitor configuration after initialization.

        Collects all validation errors and raises a single ValidationError
        with all errors, so the user can see everything that needs fixing.
        """
        errors = []

        # Validate required fields are present and correct types
        if not isinstance(self.include_paths, list):
            errors.append(f"monitor.include_paths must be a list (found: {type(self.include_paths).__name__} = {self.include_paths!r}, expected: list)")

        if not isinstance(self.exclude_paths, list):
            errors.append(f"monitor.exclude_paths must be a list (found: {type(self.exclude_paths).__name__} = {self.exclude_paths!r}, expected: list)")

        if not isinstance(self.include_dirnames, list):
            errors.append(f"monitor.include_dirnames must be a list (found: {type(self.include_dirnames).__name__} = {self.include_dirnames!r}, expected: list)")

        if not isinstance(self.exclude_dirnames, list):
            errors.append(f"monitor.exclude_dirnames must be a list (found: {type(self.exclude_dirnames).__name__} = {self.exclude_dirnames!r}, expected: list)")

        if not isinstance(self.include_globs, list):
            errors.append(f"monitor.include_globs must be a list (found: {type(self.include_globs).__name__} = {self.include_globs!r}, expected: list)")

        if not isinstance(self.exclude_globs, list):
            errors.append(f"monitor.exclude_globs must be a list (found: {type(self.exclude_globs).__name__} = {self.exclude_globs!r}, expected: list)")

        if not isinstance(self.managed_directories, dict):
            errors.append(f"monitor.managed_directories must be a dict (found: {type(self.managed_directories).__name__} = {self.managed_directories!r}, expected: dict)")

        if not isinstance(self.database, str) or "." not in self.database:
            errors.append(f"monitor.database must be in format 'database.collection' (found: {self.database!r}, expected: format like 'wks.monitor')")
        elif isinstance(self.database, str):
            parts = self.database.split(".", 1)
            if len(parts) != 2 or not parts[0] or not parts[1]:
                errors.append(f"monitor.database must be in format 'database.collection' (found: {self.database!r}, expected: format like 'wks.monitor' with both parts non-empty)")

        if not isinstance(self.touch_weight, (int, float)) or self.touch_weight < 0.001 or self.touch_weight > 1.0:
            errors.append(f"monitor.touch_weight must be a number between 0.001 and 1 (found: {type(self.touch_weight).__name__} = {self.touch_weight!r}, expected: float between 0.001 and 1.0)")

        if not isinstance(self.max_documents, int) or self.max_documents < 0:
            errors.append(f"monitor.max_documents must be a non-negative integer (found: {type(self.max_documents).__name__} = {self.max_documents!r}, expected: integer >= 0)")

        if not isinstance(self.prune_interval_secs, (int, float)) or self.prune_interval_secs <= 0:
            errors.append(f"monitor.prune_interval_secs must be a positive number (found: {type(self.prune_interval_secs).__name__} = {self.prune_interval_secs!r}, expected: float > 0)")

        if errors:
            raise ValidationError(errors)

    @classmethod
    def from_config_dict(cls, config: dict) -> "MonitorConfig":
        """Load monitor config from config dict.

        Raises:
            KeyError: If monitor section is missing
            ValidationError: If field values are invalid (contains all validation errors)
        """
        monitor_config = config.get("monitor")
        if not monitor_config:
            raise KeyError("monitor section is required in config (found: missing, expected: monitor section with include_paths, exclude_paths, etc.)")

        monitor_config = dict(monitor_config)

        allowed = {f.name for f in fields(cls)}
        unsupported = [key for key in monitor_config.keys() if key not in allowed]
        if unsupported:
            errors = [
                (
                    "Unsupported monitor config key '"
                    + key
                    + "' (remove it; supported keys: "
                    + ", ".join(sorted(allowed))
                    + ")"
                )
                for key in unsupported
            ]
            raise ValidationError(errors)

        return cls(**{k: monitor_config[k] for k in allowed})


@dataclass
class ConfigValidationResult:
    """Result of validate_config()."""
    issues: List[str] = field(default_factory=list)
    redundancies: List[str] = field(default_factory=list)
    managed_directories: Dict[str, ManagedDirectoryInfo] = field(default_factory=dict)
    include_paths: List[str] = field(default_factory=list)
    exclude_paths: List[str] = field(default_factory=list)
    include_dirnames: List[str] = field(default_factory=list)
    exclude_dirnames: List[str] = field(default_factory=list)
    include_globs: List[str] = field(default_factory=list)
    exclude_globs: List[str] = field(default_factory=list)
    include_dirname_validation: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    exclude_dirname_validation: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    include_glob_validation: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    exclude_glob_validation: Dict[str, Dict[str, Any]] = field(default_factory=dict)


@dataclass
class MonitorStatus:
    """Monitor status data structure."""
    tracked_files: int
    issues: List[str] = field(default_factory=list)
    redundancies: List[str] = field(default_factory=list)
    managed_directories: Dict[str, ManagedDirectoryInfo] = field(default_factory=dict)
    include_paths: List[str] = field(default_factory=list)
    exclude_paths: List[str] = field(default_factory=list)
    include_dirnames: List[str] = field(default_factory=list)
    exclude_dirnames: List[str] = field(default_factory=list)
    include_globs: List[str] = field(default_factory=list)
    exclude_globs: List[str] = field(default_factory=list)
    include_dirname_validation: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    exclude_dirname_validation: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    include_glob_validation: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    exclude_glob_validation: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def __post_init__(self):
        """Validate after initialization."""
        if self.tracked_files < 0:
            raise ValueError(f"MonitorStatus.tracked_files must be non-negative (found: {self.tracked_files}, expected: integer >= 0)")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization using dataclasses.asdict."""
        return asdict(self)


class MonitorController:
    """Controller for monitor operations - returns data structures for any view."""

    @staticmethod
    def get_list(config: dict, list_name: str) -> dict:
        """Get contents of a monitor config list.

        Args:
            config: Configuration dictionary
            list_name: Name of list (include/exclude paths, dirnames, or globs)

        Returns:
            dict with 'list_name', 'items' (list), and optional validation info

        Raises:
            KeyError: If monitor section or list_name is missing
        """
        monitor_cfg = MonitorConfig.from_config_dict(config)
        supported_lists = {
            "include_paths": monitor_cfg.include_paths,
            "exclude_paths": monitor_cfg.exclude_paths,
            "include_dirnames": monitor_cfg.include_dirnames,
            "exclude_dirnames": monitor_cfg.exclude_dirnames,
            "include_globs": monitor_cfg.include_globs,
            "exclude_globs": monitor_cfg.exclude_globs,
        }
        if list_name not in supported_lists:
            raise ValueError(
                f"Unknown list_name: {list_name} (found: {list_name!r}, expected one of {', '.join(sorted(supported_lists.keys()))})"
            )
        items = supported_lists[list_name]

        result = {
            "list_name": list_name,
            "items": items,
            "count": len(items)
        }

        # Include/exclude dirname validation
        if list_name in ("include_dirnames", "exclude_dirnames"):
            validation = {}
            related_globs = monitor_cfg.include_globs if list_name == "include_dirnames" else monitor_cfg.exclude_globs
            relation = "include" if list_name == "include_dirnames" else "exclude"
            for dirname in items:
                is_valid, error_msg = MonitorValidator.validate_dirname_entry(dirname)
                if is_valid:
                    redundancy = MonitorValidator.dirname_redundancy(dirname, related_globs, relation)
                    if redundancy:
                        validation[dirname] = {"valid": True, "error": redundancy}
                        continue
                validation[dirname] = {"valid": is_valid, "error": error_msg}
            result["validation"] = validation
        elif list_name in ("include_globs", "exclude_globs"):
            validation = {}
            for pattern in items:
                is_valid, error_msg = MonitorValidator.validate_glob_pattern(pattern)
                validation[pattern] = {"valid": is_valid, "error": error_msg}
            result["validation"] = validation

        return result

    @staticmethod
    def add_to_list(config_dict: dict, list_name: str, value: str, resolve_path: bool = True) -> ListOperationResult:
        """Add value to a monitor config list.

        Args:
            config_dict: Configuration dictionary (will be modified)
            list_name: Name of list to modify
            value: Value to add
            resolve_path: Whether to resolve paths (for include/exclude_paths)

        Returns:
            dict with 'success' (bool), 'message' (str), 'value_stored' (str if success)
        """
        # Ensure monitor section exists
        if "monitor" not in config_dict:
            config_dict["monitor"] = {}
        if list_name not in config_dict["monitor"]:
            config_dict["monitor"][list_name] = []

        # Normalize value if needed
        if resolve_path:
            value_resolved = _canonicalize_path(value)
            # Preserve tilde notation if in home directory
            home_dir = str(Path.home())
            if value_resolved.startswith(home_dir):
                value_to_store = "~" + value_resolved[len(home_dir):]
            else:
                value_to_store = value_resolved
        else:
            value_resolved = value
            value_to_store = value

        if list_name in ("include_dirnames", "exclude_dirnames"):
            entry = value.strip()
            is_valid, error_msg = MonitorValidator.validate_dirname_entry(entry)
            if not is_valid:
                return ListOperationResult(success=False, message=error_msg or "Invalid directory name", validation_failed=True)
            opposite = "exclude_dirnames" if list_name == "include_dirnames" else "include_dirnames"
            if entry in config_dict["monitor"].get(opposite, []):
                return ListOperationResult(
                    success=False,
                    message=f"Directory name '{entry}' already present in {opposite}",
                    validation_failed=True,
                )
            value_resolved = entry
            value_to_store = entry
        elif list_name in ("include_globs", "exclude_globs"):
            entry = value.strip()
            is_valid, error_msg = MonitorValidator.validate_glob_pattern(entry)
            if not is_valid:
                return ListOperationResult(success=False, message=error_msg or "Invalid glob pattern", validation_failed=True)
            value_resolved = entry
            value_to_store = entry

        # Check if already exists
        existing = None
        for item in config_dict["monitor"][list_name]:
            if resolve_path:
                item_resolved = _canonicalize_path(item)
                if item_resolved == value_resolved:
                    existing = item
                    break
            else:
                if item == value_resolved:
                    existing = item
                    break

        if existing:
            return ListOperationResult(
                success=False,
                message=f"Already in {list_name}: {existing}",
                already_exists=True
            )

        # Add to list
        config_dict["monitor"][list_name].append(value_to_store)
        return ListOperationResult(
            success=True,
            message=f"Added to {list_name}: {value_to_store}",
            value_stored=value_to_store
        )

    @staticmethod
    def remove_from_list(config_dict: dict, list_name: str, value: str, resolve_path: bool = True) -> ListOperationResult:
        """Remove value from a monitor config list.

        Args:
            config_dict: Configuration dictionary (will be modified)
            list_name: Name of list to modify
            value: Value to remove
            resolve_path: Whether to resolve paths (for include/exclude_paths)

        Returns:
            dict with 'success' (bool), 'message' (str), 'value_removed' (str if success)
        """
        if "monitor" not in config_dict or list_name not in config_dict["monitor"]:
            return ListOperationResult(
                success=False,
                message=f"No {list_name} configured",
                not_found=True
            )

        # Find matching entry
        existing = None
        if resolve_path:
            value_resolved = _canonicalize_path(value)
            for item in config_dict["monitor"][list_name]:
                item_resolved = _canonicalize_path(item)
                if item_resolved == value_resolved:
                    existing = item
                    break
        else:
            if list_name in ("include_dirnames", "exclude_dirnames", "include_globs", "exclude_globs"):
                search_value = value.strip()
            else:
                search_value = value
            for item in config_dict["monitor"][list_name]:
                if item == search_value:
                    existing = item
                    break

        if not existing:
            return ListOperationResult(
                success=False,
                message=f"Not in {list_name}: {value}",
                not_found=True
            )

        # Remove from list
        config_dict["monitor"][list_name].remove(existing)
        return ListOperationResult(
            success=True,
            message=f"Removed from {list_name}: {existing}",
            value_removed=existing
        )

    @staticmethod
    def get_managed_directories(config: dict) -> ManagedDirectoriesResult:
        """Get managed directories with their priorities.

        Args:
            config: Configuration dictionary

        Returns:
            dict with 'managed_directories' (dict of path->priority), 'count', and validation info

        Raises:
            KeyError: If monitor section or required fields are missing
        """
        monitor_cfg = MonitorConfig.from_config_dict(config)

        # Validate each managed directory
        validation = {}
        rules = MonitorRules.from_config(monitor_cfg)
        for path, priority in monitor_cfg.managed_directories.items():
            is_valid, error_msg = MonitorValidator.validate_managed_directory(
                path, rules
            )
            validation[path] = ManagedDirectoryInfo(
                priority=priority,
                valid=is_valid,
                error=error_msg
            )

        return ManagedDirectoriesResult(
            managed_directories=monitor_cfg.managed_directories,
            count=len(monitor_cfg.managed_directories),
            validation=validation
        )

    @staticmethod
    def add_managed_directory(config_dict: dict, path: str, priority: int) -> dict:
        """Add a managed directory with priority.

        Args:
            config_dict: Configuration dictionary (will be modified)
            path: Directory path to add
            priority: Priority score

        Returns:
            dict with 'success' (bool), 'message' (str), 'path_stored' (str if success)
        """
        # Ensure sections exist
        if "monitor" not in config_dict:
            config_dict["monitor"] = {}
        if "managed_directories" not in config_dict["monitor"]:
            config_dict["monitor"]["managed_directories"] = {}

        # Resolve path
        path_resolved = _canonicalize_path(path)

        # Check if already exists
        existing_key = _find_matching_path_key(config_dict["monitor"]["managed_directories"], path_resolved)
        if existing_key is not None:
            return {
                "success": False,
                "message": f"Already a managed directory: {existing_key}",
                "already_exists": True
            }

        # Add to managed directories
        config_dict["monitor"]["managed_directories"][path_resolved] = priority

        return {
            "success": True,
            "message": f"Added managed directory: {path_resolved} (priority {priority})",
            "path_stored": path_resolved,
            "priority": priority
        }

    @staticmethod
    def remove_managed_directory(config_dict: dict, path: str) -> dict:
        """Remove a managed directory.

        Args:
            config_dict: Configuration dictionary (will be modified)
            path: Directory path to remove

        Returns:
            dict with 'success' (bool), 'message' (str), 'path_removed' (str if success)
        """
        if "monitor" not in config_dict or "managed_directories" not in config_dict["monitor"]:
            return {
                "success": False,
                "message": "No managed_directories configured",
                "not_found": True
            }

        # Resolve path
        path_resolved = _canonicalize_path(path)
        existing_key = _find_matching_path_key(config_dict["monitor"]["managed_directories"], path_resolved)

        # Check if exists
        if existing_key is None:
            return {
                "success": False,
                "message": f"Not a managed directory: {path_resolved}",
                "not_found": True
            }

        # Get priority before removing
        priority = config_dict["monitor"]["managed_directories"][existing_key]

        # Remove from managed directories
        del config_dict["monitor"]["managed_directories"][existing_key]

        return {
            "success": True,
            "message": f"Removed managed directory: {existing_key}",
            "path_removed": existing_key,
            "priority": priority
        }

    @staticmethod
    def set_managed_priority(config_dict: dict, path: str, priority: int) -> dict:
        """Update priority for a managed directory.

        Args:
            config_dict: Configuration dictionary (will be modified)
            path: Directory path
            priority: New priority score

        Returns:
            dict with 'success' (bool), 'message' (str), 'old_priority', 'new_priority'
        """
        if "monitor" not in config_dict or "managed_directories" not in config_dict["monitor"]:
            return {
                "success": False,
                "message": "No managed_directories configured",
                "not_found": True
            }

        # Resolve path
        path_resolved = _canonicalize_path(path)
        existing_key = _find_matching_path_key(config_dict["monitor"]["managed_directories"], path_resolved)

        # Check if exists
        if existing_key is None:
            return {
                "success": False,
                "message": f"Not a managed directory: {path_resolved}",
                "not_found": True
            }

        # Get old priority
        old_priority = config_dict["monitor"]["managed_directories"][existing_key]

        # Update priority
        config_dict["monitor"]["managed_directories"][existing_key] = priority

        return {
            "success": True,
            "message": f"Updated priority for {existing_key}: {old_priority} → {priority}",
            "path": existing_key,
            "old_priority": old_priority,
            "new_priority": priority
        }

    @staticmethod
    def get_status(config: Dict[str, Any]) -> MonitorStatus:
        """Get monitor status, including validation issues.

        Raises:
            KeyError: If monitor section is missing
        """
        from .config import mongo_settings
        from pymongo import MongoClient

        monitor_cfg = MonitorConfig.from_config_dict(config)
        mongo_config = mongo_settings(config)

        # Get total tracked files
        try:
            client = MongoClient(mongo_config["uri"], serverSelectionTimeoutMS=5000)
            client.server_info()
            db_name, coll_name = monitor_cfg.database.split(".", 1)
            db = client[db_name]
            collection = db[coll_name]
            total_files = collection.count_documents({})
            client.close()
        except Exception:
            total_files = 0

        # Get config validation
        validation = MonitorController.validate_config(config)

        return MonitorStatus(
            tracked_files=total_files,
            issues=validation.issues,
            redundancies=validation.redundancies,
            managed_directories=validation.managed_directories,
            include_paths=validation.include_paths,
            exclude_paths=validation.exclude_paths,
            include_dirnames=validation.include_dirnames,
            exclude_dirnames=validation.exclude_dirnames,
            include_globs=validation.include_globs,
            exclude_globs=validation.exclude_globs,
            include_dirname_validation=validation.include_dirname_validation,
            exclude_dirname_validation=validation.exclude_dirname_validation,
            include_glob_validation=validation.include_glob_validation,
            exclude_glob_validation=validation.exclude_glob_validation,
        )

    @staticmethod
    def validate_config(config: dict) -> ConfigValidationResult:
        """Validate monitor configuration for conflicts and issues.

        Raises:
            KeyError: If monitor section or required fields are missing
        """
        monitor_cfg = MonitorConfig.from_config_dict(config)
        rules = MonitorRules.from_config(monitor_cfg)

        include_map = _build_canonical_map(monitor_cfg.include_paths)
        exclude_map = _build_canonical_map(monitor_cfg.exclude_paths)
        include_paths = set(include_map.keys())
        exclude_paths = set(exclude_map.keys())
        managed_dirs = list(monitor_cfg.managed_directories.keys())

        issues: List[str] = []
        redundancies: List[str] = []
        managed_directories: Dict[str, ManagedDirectoryInfo] = {}
        include_dirname_validation: Dict[str, Dict[str, Any]] = {}
        exclude_dirname_validation: Dict[str, Dict[str, Any]] = {}
        include_glob_validation: Dict[str, Dict[str, Any]] = {}
        exclude_glob_validation: Dict[str, Dict[str, Any]] = {}

        # Paths present in both include/exclude lists
        for canonical in sorted(include_paths & exclude_paths):
            includes = include_map.get(canonical, [])
            excludes = exclude_map.get(canonical, [])
            issues.append(
                f"Path listed in both include_paths and exclude_paths after resolving to {canonical}: include [{', '.join(includes)}], exclude [{', '.join(excludes)}]"
            )

        # Duplicate canonical entries within the same list
        for canonical, raw_paths in include_map.items():
            if len(raw_paths) > 1:
                redundancies.append(f"include_paths entries {raw_paths} resolve to the same path ({canonical})")
        for canonical, raw_paths in exclude_map.items():
            if len(raw_paths) > 1:
                redundancies.append(f"exclude_paths entries {raw_paths} resolve to the same path ({canonical})")

        # Warn about redundant exclude paths automatically ignored
        wks_home = _canonicalize_path("~/.wks")
        if wks_home in exclude_map:
            for entry in exclude_map[wks_home]:
                redundancies.append(f"exclude_paths entry '{entry}' is redundant - WKS home is automatically ignored")

        vault_base = config.get("vault", {}).get("base_dir")
        if vault_base:
            vault_resolved = _canonicalize_path(vault_base)
            if vault_resolved in exclude_map:
                for entry in exclude_map[vault_resolved]:
                    redundancies.append(f"exclude_paths entry '{entry}' is redundant - vault.base_dir is managed separately")

        # Managed directory validation
        for path, priority in monitor_cfg.managed_directories.items():
            is_valid, error_msg = MonitorValidator.validate_managed_directory(path, rules)
            managed_directories[path] = ManagedDirectoryInfo(priority=priority, valid=is_valid, error=error_msg)
            if not is_valid:
                issues.append(f"managed_directories entry '{path}' would NOT be monitored: {error_msg}")

        # Duplicate managed directories (same resolved path)
        for i, dir1 in enumerate(managed_dirs):
            p1 = Path(dir1).expanduser().resolve()
            for dir2 in managed_dirs[i + 1:]:
                p2 = Path(dir2).expanduser().resolve()
                if p1 == p2:
                    redundancies.append(f"Duplicate managed directories: {dir1} and {dir2} resolve to the same path")

        # Dirname validations
        include_dirname_set = set()
        exclude_dirname_set = set()
        for dirname in monitor_cfg.include_dirnames:
            is_valid, error_msg = MonitorValidator.validate_dirname_entry(dirname)
            include_dirname_set.add(dirname)
            if not is_valid:
                issues.append(f"include_dirnames entry '{dirname}': {error_msg}")
            else:
                redundancy = MonitorValidator.dirname_redundancy(dirname, monitor_cfg.include_globs, "include")
                if redundancy:
                    redundancies.append(f"include_dirnames entry '{dirname}': {redundancy}")
                    error_msg = redundancy
            include_dirname_validation[dirname] = {"valid": is_valid, "error": error_msg}

        for dirname in monitor_cfg.exclude_dirnames:
            is_valid, error_msg = MonitorValidator.validate_dirname_entry(dirname)
            exclude_dirname_set.add(dirname)
            if not is_valid:
                issues.append(f"exclude_dirnames entry '{dirname}': {error_msg}")
            else:
                redundancy = MonitorValidator.dirname_redundancy(dirname, monitor_cfg.exclude_globs, "exclude")
                if redundancy:
                    redundancies.append(f"exclude_dirnames entry '{dirname}': {redundancy}")
                    error_msg = redundancy
            exclude_dirname_validation[dirname] = {"valid": is_valid, "error": error_msg}

        duplicates = include_dirname_set & exclude_dirname_set
        for dirname in sorted(duplicates):
            issues.append(f"Directory name '{dirname}' appears in both include_dirnames and exclude_dirnames")

        # Glob validations
        for pattern in monitor_cfg.include_globs:
            is_valid, error_msg = MonitorValidator.validate_glob_pattern(pattern)
            include_glob_validation[pattern] = {"valid": is_valid, "error": error_msg}
            if not is_valid:
                issues.append(f"include_globs entry '{pattern}': {error_msg}")

        for pattern in monitor_cfg.exclude_globs:
            is_valid, error_msg = MonitorValidator.validate_glob_pattern(pattern)
            exclude_glob_validation[pattern] = {"valid": is_valid, "error": error_msg}
            if not is_valid:
                issues.append(f"exclude_globs entry '{pattern}': {error_msg}")

        return ConfigValidationResult(
            issues=issues,
            redundancies=redundancies,
            managed_directories=managed_directories,
            include_paths=monitor_cfg.include_paths,
            exclude_paths=monitor_cfg.exclude_paths,
            include_dirnames=monitor_cfg.include_dirnames,
            exclude_dirnames=monitor_cfg.exclude_dirnames,
            include_globs=monitor_cfg.include_globs,
            exclude_globs=monitor_cfg.exclude_globs,
            include_dirname_validation=include_dirname_validation,
            exclude_dirname_validation=exclude_dirname_validation,
            include_glob_validation=include_glob_validation,
            exclude_glob_validation=exclude_glob_validation,
        )

    @staticmethod
    def check_path(config: dict, path_str: str) -> dict:
        """Check if a path would be monitored and calculate its priority.

        Raises:
            KeyError: If monitor section or required fields are missing
        """
        from .priority import calculate_priority

        monitor_cfg = MonitorConfig.from_config_dict(config)
        rules = MonitorRules.from_config(monitor_cfg)

        # Resolve path
        test_path = Path(path_str).expanduser().resolve()

        decisions = []
        path_exists = test_path.exists()
        decisions.append({
            "symbol": "✓" if path_exists else "⚠",
            "message": f"Path exists: {test_path}" if path_exists else f"Path does not exist (checking as if it did): {test_path}"
        })

        allowed, trace = rules.explain(test_path)
        for message in trace:
            lower = message.lower()
            if lower.startswith("excluded"):
                symbol = "✗"
            elif "override" in lower or lower.startswith("included"):
                symbol = "✓"
            else:
                symbol = "•"
            decisions.append({"symbol": symbol, "message": message})

        if not allowed:
            return {
                "path": str(test_path),
                "is_monitored": False,
                "reason": trace[-1] if trace else "Excluded by monitor rules",
                "priority": None,
                "decisions": decisions
            }

        # Calculate priority
        try:
            priority = calculate_priority(test_path, monitor_cfg.managed_directories, monitor_cfg.priority)
            decisions.append({"symbol": "✓", "message": f"Priority calculated: {priority}"})
        except Exception as e:
            priority = None
            decisions.append({"symbol": "⚠", "message": f"Could not calculate priority: {e}"})

        return {
            "path": str(test_path),
            "is_monitored": True,
            "reason": "Would be monitored",
            "priority": priority,
            "decisions": decisions
        }

    @staticmethod
    def prune_ignored_files(config: dict) -> dict:
        """Prune ignored files from the monitor database."""
        from .config import mongo_settings
        from .uri_utils import uri_to_path
        from pymongo import MongoClient
        import os

        monitor_cfg = MonitorConfig.from_config_dict(config)
        mongo_config = mongo_settings(config)

        try:
            client = MongoClient(mongo_config["uri"], serverSelectionTimeoutMS=5000)
            client.server_info()  # Will raise an exception if connection fails
            db_name, coll_name = monitor_cfg.database.split(".", 1)
            db = client[db_name]
            collection = db[coll_name]
        except Exception as e:
            return {"success": False, "errors": [f"DB connection failed: {e}"], "pruned_files": []}

        rules = MonitorRules.from_config(monitor_cfg)

        pruned_files = []
        errors = []
        processed_count = 0

        try:
            for doc in collection.find():
                processed_count += 1
                uri = doc.get("path")
                if not uri:
                    continue

                try:
                    # The URI in the DB is the canonical representation
                    path_to_check = uri_to_path(uri)
                except Exception as e:
                    errors.append(f"Error converting URI {uri}: {e}")
                    continue

                if not rules.allows(path_to_check):
                    pruned_files.append(str(path_to_check))
                    collection.delete_one({"_id": doc["_id"]})
        except Exception as e:
            errors.append(f"An error occurred during pruning: {e}")
        finally:
            client.close()

        return {
            "success": not errors,
            "pruned_count": len(pruned_files),
            "processed_count": processed_count,
            "pruned_files": pruned_files,
            "errors": errors,
        }

    @staticmethod
    def prune_deleted_files(config: dict) -> dict:
        """Prune deleted files from the monitor database."""
        from .config import mongo_settings
        from .uri_utils import uri_to_path
        from pymongo import MongoClient

        monitor_cfg = MonitorConfig.from_config_dict(config)
        mongo_config = mongo_settings(config)

        try:
            client = MongoClient(mongo_config["uri"], serverSelectionTimeoutMS=5000)
            client.server_info()
            db_name, coll_name = monitor_cfg.database.split(".", 1)
            db = client[db_name]
            collection = db[coll_name]
        except Exception as e:
            return {"success": False, "errors": [f"DB connection failed: {e}"], "pruned_files": []}

        pruned_files = []
        errors = []
        processed_count = 0

        try:
            for doc in collection.find():
                processed_count += 1
                uri = doc.get("path")
                if not uri:
                    continue

                try:
                    path = uri_to_path(uri)
                except Exception as e:
                    errors.append(f"Error converting URI {uri}: {e}")
                    continue

                if not path.exists():
                    pruned_files.append(str(path))
                    collection.delete_one({"_id": doc["_id"]})
        except Exception as e:
            errors.append(f"An error occurred during pruning: {e}")
        finally:
            client.close()

        return {
            "success": not errors,
            "pruned_count": len(pruned_files),
            "processed_count": processed_count,
            "pruned_files": pruned_files,
            "errors": errors,
        }
