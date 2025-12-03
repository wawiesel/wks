"""Monitor Controller - Business logic for filesystem monitoring operations."""

from pathlib import Path
from typing import Dict, List, Tuple, Any

from ..monitor_rules import MonitorRules
from .config import MonitorConfig
from .status import (
    MonitorStatus,
    ConfigValidationResult,
    ManagedDirectoryInfo,
    ManagedDirectoriesResult,
)
from .validator import MonitorValidator
from .operations import MonitorOperations, _canonicalize_path


def _build_canonical_map(values: List[str]) -> Dict[str, List[str]]:
    """Map canonical path strings to the original representations."""
    mapping: Dict[str, List[str]] = {}
    for raw in values:
        canonical = _canonicalize_path(raw)
        mapping.setdefault(canonical, []).append(raw)
    return mapping


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

    # Delegate to MonitorOperations
    add_to_list = staticmethod(MonitorOperations.add_to_list)
    remove_from_list = staticmethod(MonitorOperations.remove_from_list)
    add_managed_directory = staticmethod(MonitorOperations.add_managed_directory)
    remove_managed_directory = staticmethod(MonitorOperations.remove_managed_directory)
    set_managed_priority = staticmethod(MonitorOperations.set_managed_priority)

    @staticmethod
    def get_managed_directories(config: dict) -> ManagedDirectoriesResult:
        """Get managed directories with their priorities.

        Args:
            config: Configuration dictionary

        Returns:
            ManagedDirectoriesResult with managed directories, count, and validation

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
    def get_status(config: Dict[str, Any]) -> MonitorStatus:
        """Get monitor status, including validation issues.

        Raises:
            KeyError: If monitor section is missing
        """
        from ..config import WKSConfig
        from pymongo import MongoClient

        if hasattr(config, "monitor"):
            monitor_cfg = config.monitor
        else:
            monitor_cfg = MonitorConfig.from_config_dict(config)
        try:
            wks_config = WKSConfig.load()
            mongo_uri = wks_config.mongo.uri
        except Exception:
            mongo_uri = "mongodb://localhost:27017"

        # Get total tracked files
        try:
            client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
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
    def _validate_path_conflicts(include_map: Dict, exclude_map: Dict) -> List[str]:
        """Validate paths aren't in both include and exclude lists."""
        issues = []
        include_paths = set(include_map.keys())
        exclude_paths = set(exclude_map.keys())

        for canonical in sorted(include_paths & exclude_paths):
            includes = include_map.get(canonical, [])
            excludes = exclude_map.get(canonical, [])
            issues.append(
                f"Path listed in both include_paths and exclude_paths after resolving to {canonical}: include [{', '.join(includes)}], exclude [{', '.join(excludes)}]"
            )
        return issues

    @staticmethod
    def _validate_path_redundancy(include_map: Dict, exclude_map: Dict, config: dict) -> List[str]:
        """Validate duplicate canonical paths and auto-ignored paths."""
        redundancies = []

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

        return redundancies

    @staticmethod
    def _validate_managed_directories(monitor_cfg: MonitorConfig, rules: MonitorRules) -> Tuple[List[str], List[str], Dict[str, ManagedDirectoryInfo]]:
        """Validate managed directories."""
        issues = []
        redundancies = []
        managed_directories = {}
        managed_dirs = list(monitor_cfg.managed_directories.keys())

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

        return issues, redundancies, managed_directories

    @staticmethod
    def _validate_dirnames(monitor_cfg: MonitorConfig) -> Tuple[List[str], List[str], Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
        """Validate include/exclude dirnames."""
        issues = []
        redundancies = []
        include_dirname_validation = {}
        exclude_dirname_validation = {}
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

        return issues, redundancies, include_dirname_validation, exclude_dirname_validation

    @staticmethod
    def _validate_globs(monitor_cfg: MonitorConfig) -> Tuple[List[str], Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
        """Validate include/exclude glob patterns."""
        issues = []
        include_glob_validation = {}
        exclude_glob_validation = {}

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

        return issues, include_glob_validation, exclude_glob_validation

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

        # Collect all validation results
        issues = []
        redundancies = []

        # Path conflicts
        issues.extend(MonitorController._validate_path_conflicts(include_map, exclude_map))

        # Path redundancy
        redundancies.extend(MonitorController._validate_path_redundancy(include_map, exclude_map, config))

        # Managed directories
        mgd_issues, mgd_redundancies, managed_directories = MonitorController._validate_managed_directories(monitor_cfg, rules)
        issues.extend(mgd_issues)
        redundancies.extend(mgd_redundancies)

        # Dirnames
        dir_issues, dir_redundancies, include_dirname_validation, exclude_dirname_validation = MonitorController._validate_dirnames(monitor_cfg)
        issues.extend(dir_issues)
        redundancies.extend(dir_redundancies)

        # Globs
        glob_issues, include_glob_validation, exclude_glob_validation = MonitorController._validate_globs(monitor_cfg)
        issues.extend(glob_issues)

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
        from ..priority import calculate_priority

        from ..config import WKSConfig

        if isinstance(config, WKSConfig):
            monitor_cfg = config.monitor
        else:
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
        from ..config import WKSConfig
        from ..uri_utils import uri_to_path
        from pymongo import MongoClient

        if isinstance(config, WKSConfig):
            monitor_cfg = config.monitor
        else:
            monitor_cfg = MonitorConfig.from_config_dict(config)
        try:
            wks_config = WKSConfig.load()
            mongo_uri = wks_config.mongo.uri
        except Exception:
            mongo_uri = "mongodb://localhost:27017"

        try:
            client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
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
        from ..config import WKSConfig
        from ..uri_utils import uri_to_path
        from pymongo import MongoClient

        if isinstance(config, WKSConfig):
            monitor_cfg = config.monitor
        else:
            monitor_cfg = MonitorConfig.from_config_dict(config)
        try:
            wks_config = WKSConfig.load()
            mongo_uri = wks_config.mongo.uri
        except Exception:
            mongo_uri = "mongodb://localhost:27017"

        try:
            client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
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
