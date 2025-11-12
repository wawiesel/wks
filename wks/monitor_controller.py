"""
Monitor Controller - Business logic for filesystem monitoring operations.

This module contains all monitor-related business logic, completely separated
from the CLI display layer. This enables:
- Easy unit testing
- Reuse by MCP server
- Zero code duplication per SPEC.md
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import fnmatch
import math


class MonitorValidator:
    """Validation logic for monitor configuration."""

    @staticmethod
    def status_symbol(error_msg: Optional[str], is_valid: bool = True) -> str:
        """Convert validation result to colored status symbol."""
        return "[green]✓[/]" if not error_msg else "[yellow]⚠[/]" if is_valid else "[red]✗[/]"

    @staticmethod
    def validate_ignore_dirname(dirname: str, ignore_globs: List[str]) -> Tuple[bool, Optional[str]]:
        """Validate an ignore_dirname entry."""
        if '*' in dirname or '?' in dirname or '[' in dirname:
            return False, "ignore_dirnames cannot contain wildcard characters (*, ?, [). Use ignore_globs for patterns."

        for glob_pattern in ignore_globs:
            if fnmatch.fnmatch(dirname, glob_pattern):
                return True, f"Redundant: dirname '{dirname}' already matched by ignore_globs pattern '{glob_pattern}'"

        return True, None

    @staticmethod
    def validate_ignore_glob(pattern: str) -> Tuple[bool, Optional[str]]:
        """Validate an ignore_glob pattern for syntax errors."""
        try:
            fnmatch.fnmatch("test", pattern)
            return True, None
        except Exception as e:
            return False, f"Invalid glob syntax: {str(e)}"

    @staticmethod
    def validate_managed_directory(
        managed_path: str,
        include_paths: List[str],
        exclude_paths: List[str],
        ignore_dirnames: List[str],
        ignore_globs: List[str]
    ) -> Tuple[bool, Optional[str]]:
        """Validate that a managed_directory would actually be monitored."""
        managed_resolved = Path(managed_path).expanduser().resolve()

        # Check for system paths that are always ignored
        wks_home = Path("~/.wks").expanduser().resolve()
        if managed_resolved == wks_home or str(managed_resolved).startswith(str(wks_home) + "/"):
            return False, "In WKS home directory (automatically ignored)"

        if ".wkso" in managed_resolved.parts:
            return False, "Contains .wkso directory (automatically ignored)"

        # Check if under any include_paths
        if not any(managed_resolved.is_relative_to(Path(p).expanduser().resolve())
                  for p in include_paths):
            return False, "Not under any include_paths"

        # Check if in exclude_paths
        for exclude_path in exclude_paths:
            try:
                if managed_resolved.is_relative_to(Path(exclude_path).expanduser().resolve()):
                    return False, f"Matched by exclude_paths: {exclude_path}"
            except:
                pass

        # Check if any path component matches ignore_dirnames
        for part in managed_resolved.parts:
            if part in ignore_dirnames:
                return False, f"Contains ignored dirname: {part}"

        # Check if matches ignore_globs
        for glob_pattern in ignore_globs:
            if fnmatch.fnmatch(str(managed_resolved), glob_pattern) or \
               fnmatch.fnmatch(managed_resolved.name, glob_pattern):
                return False, f"Matched by ignore_globs: {glob_pattern}"

        return True, None


class MonitorController:
    """Controller for monitor operations - returns data structures for any view."""

    @staticmethod
    def get_list(config: dict, list_name: str) -> dict:
        """Get contents of a monitor config list.

        Args:
            config: Configuration dictionary
            list_name: Name of list (include_paths, exclude_paths, ignore_dirnames, ignore_globs)

        Returns:
            dict with 'list_name', 'items' (list), and optional validation info
        """
        monitor_config = config.get("monitor", {})
        items = monitor_config.get(list_name, [])

        result = {
            "list_name": list_name,
            "items": items,
            "count": len(items)
        }

        # Add validation for ignore_dirnames
        if list_name == "ignore_dirnames":
            ignore_globs = monitor_config.get("ignore_globs", [])
            validation = {}
            for dirname in items:
                is_valid, error_msg = MonitorValidator.validate_ignore_dirname(dirname, ignore_globs)
                validation[dirname] = {"valid": is_valid, "error": error_msg}
            result["validation"] = validation

        # Add validation for ignore_globs
        elif list_name == "ignore_globs":
            validation = {}
            for pattern in items:
                is_valid, error_msg = MonitorValidator.validate_ignore_glob(pattern)
                validation[pattern] = {"valid": is_valid, "error": error_msg}
            result["validation"] = validation

        return result

    @staticmethod
    def add_to_list(config_dict: dict, list_name: str, value: str, resolve_path: bool = True) -> dict:
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
            value_resolved = str(Path(value).expanduser().resolve())
            # Preserve tilde notation if in home directory
            home_dir = str(Path.home())
            if value_resolved.startswith(home_dir):
                value_to_store = "~" + value_resolved[len(home_dir):]
            else:
                value_to_store = value_resolved
        else:
            value_resolved = value
            value_to_store = value

        # Check if already exists
        existing = None
        for item in config_dict["monitor"][list_name]:
            if resolve_path:
                item_resolved = str(Path(item).expanduser().resolve())
                if item_resolved == value_resolved:
                    existing = item
                    break
            else:
                if item == value:
                    existing = item
                    break

        if existing:
            return {
                "success": False,
                "message": f"Already in {list_name}: {existing}",
                "already_exists": True
            }

        # Validate ignore_dirnames before adding
        if list_name == "ignore_dirnames":
            ignore_globs = config_dict["monitor"].get("ignore_globs", [])
            is_valid, error_msg = MonitorValidator.validate_ignore_dirname(value, ignore_globs)
            if not is_valid:
                return {
                    "success": False,
                    "message": error_msg,
                    "validation_failed": True
                }

        # Add to list
        config_dict["monitor"][list_name].append(value_to_store)
        return {
            "success": True,
            "message": f"Added to {list_name}: {value_to_store}",
            "value_stored": value_to_store
        }

    @staticmethod
    def remove_from_list(config_dict: dict, list_name: str, value: str, resolve_path: bool = True) -> dict:
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
            return {
                "success": False,
                "message": f"No {list_name} configured",
                "not_found": True
            }

        # Find matching entry
        existing = None
        if resolve_path:
            value_resolved = str(Path(value).expanduser().resolve())
            for item in config_dict["monitor"][list_name]:
                item_resolved = str(Path(item).expanduser().resolve())
                if item_resolved == value_resolved:
                    existing = item
                    break
        else:
            if value in config_dict["monitor"][list_name]:
                existing = value

        if not existing:
            return {
                "success": False,
                "message": f"Not in {list_name}: {value}",
                "not_found": True
            }

        # Remove from list
        config_dict["monitor"][list_name].remove(existing)
        return {
            "success": True,
            "message": f"Removed from {list_name}: {existing}",
            "value_removed": existing
        }

    @staticmethod
    def get_managed_directories(config: dict) -> dict:
        """Get managed directories with their priorities.

        Args:
            config: Configuration dictionary

        Returns:
            dict with 'managed_directories' (dict of path->priority), 'count', and validation info
        """
        monitor_config = config.get("monitor", {})
        managed_dirs = monitor_config.get("managed_directories", {})
        include_paths = monitor_config.get("include_paths", [])
        exclude_paths = monitor_config.get("exclude_paths", [])
        ignore_dirnames = monitor_config.get("ignore_dirnames", [])
        ignore_globs = monitor_config.get("ignore_globs", [])

        # Validate each managed directory
        validation = {}
        for path, priority in managed_dirs.items():
            is_valid, error_msg = MonitorValidator.validate_managed_directory(
                path, include_paths, exclude_paths, ignore_dirnames, ignore_globs
            )
            validation[path] = {
                "priority": priority,
                "valid": is_valid,
                "error": error_msg
            }

        return {
            "managed_directories": managed_dirs,
            "count": len(managed_dirs),
            "validation": validation
        }

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
        path_resolved = str(Path(path).expanduser().resolve())

        # Check if already exists
        if path_resolved in config_dict["monitor"]["managed_directories"]:
            return {
                "success": False,
                "message": f"Already a managed directory: {path_resolved}",
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
        path_resolved = str(Path(path).expanduser().resolve())

        # Check if exists
        if path_resolved not in config_dict["monitor"]["managed_directories"]:
            return {
                "success": False,
                "message": f"Not a managed directory: {path_resolved}",
                "not_found": True
            }

        # Get priority before removing
        priority = config_dict["monitor"]["managed_directories"][path_resolved]

        # Remove from managed directories
        del config_dict["monitor"]["managed_directories"][path_resolved]

        return {
            "success": True,
            "message": f"Removed managed directory: {path_resolved}",
            "path_removed": path_resolved,
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
        path_resolved = str(Path(path).expanduser().resolve())

        # Check if exists
        if path_resolved not in config_dict["monitor"]["managed_directories"]:
            return {
                "success": False,
                "message": f"Not a managed directory: {path_resolved}",
                "not_found": True
            }

        # Get old priority
        old_priority = config_dict["monitor"]["managed_directories"][path_resolved]

        # Update priority
        config_dict["monitor"]["managed_directories"][path_resolved] = priority

        return {
            "success": True,
            "message": f"Updated priority for {path_resolved}: {old_priority} → {priority}",
            "path": path_resolved,
            "old_priority": old_priority,
            "new_priority": priority
        }

    @staticmethod
    def get_status(config: dict) -> dict:
        """Get monitor status as structured data (view-agnostic)."""
        monitor_config = config.get("monitor", {})

        # Extract config
        include_paths = set(monitor_config.get("include_paths", []))
        exclude_paths = set(monitor_config.get("exclude_paths", []))
        managed_dirs_dict = monitor_config.get("managed_directories", {})
        ignore_dirnames = monitor_config.get("ignore_dirnames", [])
        ignore_globs = monitor_config.get("ignore_globs", [])

        # Validation results
        issues = []
        redundancies = []

        # Validate vault_path
        vault_path = config.get("vault_path")
        if vault_path:
            vault_resolved = str(Path(vault_path).expanduser().resolve())
            for include_path in include_paths:
                if str(Path(include_path).expanduser().resolve()) == vault_resolved:
                    issues.append(f"vault_path '{vault_path}' explicitly in include_paths - vault is automatically ignored")
            for exclude_path in exclude_paths:
                if str(Path(exclude_path).expanduser().resolve()) == vault_resolved:
                    redundancies.append(f"exclude_paths entry '{exclude_path}' is redundant - vault_path is automatically ignored")

        # Validate WKS home
        wks_home = str(Path("~/.wks").expanduser().resolve())
        for include_path in include_paths:
            if str(Path(include_path).expanduser().resolve()) == wks_home:
                issues.append(f"WKS home '~/.wks' explicitly in include_paths - WKS home is automatically ignored")
        for exclude_path in exclude_paths:
            if str(Path(exclude_path).expanduser().resolve()) == wks_home:
                redundancies.append(f"exclude_paths entry '~/.wks' is redundant - WKS home is automatically ignored")

        # Check for .wkso in ignore_dirnames
        if ".wkso" in ignore_dirnames:
            redundancies.append(f"ignore_dirnames entry '.wkso' is redundant - .wkso directories are automatically ignored")

        # Validate managed directories
        managed_validation = {}
        for path, priority in managed_dirs_dict.items():
            is_valid, error_msg = MonitorValidator.validate_managed_directory(
                path, list(include_paths), list(exclude_paths), ignore_dirnames, ignore_globs
            )
            managed_validation[path] = {"priority": priority, "valid": is_valid, "error": error_msg}
            if error_msg:
                issues.append(f"managed_directories entry '{path}': {error_msg}")

            # Calculate pips for display
            pip_count = 1 if priority <= 1 else int(math.log10(priority)) + 1
            managed_validation[path]["pips"] = pip_count

        # Validate ignore rules
        ignore_dirname_validation = {}
        for dirname in ignore_dirnames:
            is_valid, error_msg = MonitorValidator.validate_ignore_dirname(dirname, ignore_globs)
            ignore_dirname_validation[dirname] = {"valid": is_valid, "error": error_msg}
            if error_msg:
                (redundancies if is_valid else issues).append(f"ignore_dirnames entry '{dirname}': {error_msg}")

        ignore_glob_validation = {}
        for pattern in ignore_globs:
            is_valid, error_msg = MonitorValidator.validate_ignore_glob(pattern)
            ignore_glob_validation[pattern] = {"valid": is_valid, "error": error_msg}
            if error_msg:
                (redundancies if is_valid else issues).append(f"ignore_globs pattern '{pattern}': {error_msg}")

        # Get DB stats
        mongo_config = config.get("mongo", {}) or config.get("db", {})
        mongo_uri = mongo_config.get("uri", "mongodb://localhost:27017/")
        db_name = monitor_config.get("database", "wks")
        coll_name = monitor_config.get("collection", "monitor")

        tracked_files = 0
        try:
            from pymongo import MongoClient
            client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
            client.server_info()
            tracked_files = client[db_name][coll_name].count_documents({})
            client.close()
        except:
            pass

        return {
            "tracked_files": tracked_files,
            "managed_directories": managed_validation,
            "include_paths": sorted(include_paths),
            "exclude_paths": sorted(exclude_paths),
            "ignore_dirnames": ignore_dirnames,
            "ignore_globs": ignore_globs,
            "ignore_dirname_validation": ignore_dirname_validation,
            "ignore_glob_validation": ignore_glob_validation,
            "issues": issues,
            "redundancies": redundancies,
            "db_name": db_name,
            "coll_name": coll_name
        }

    @staticmethod
    def validate_config(config: dict) -> dict:
        """Validate monitor configuration for conflicts and issues."""
        monitor_config = config.get("monitor", {})
        include_paths = set(monitor_config.get("include_paths", []))
        exclude_paths = set(monitor_config.get("exclude_paths", []))
        managed_dirs = set(monitor_config.get("managed_directories", {}).keys())

        issues = []
        warnings = []

        # Check 1: Paths in both include and exclude
        conflicts = include_paths & exclude_paths
        if conflicts:
            for path in conflicts:
                issues.append(f"Path in both include and exclude: {path}")

        # Check 2: Duplicate managed directories (same resolved path)
        managed_list = list(managed_dirs)
        for i, dir1 in enumerate(managed_list):
            p1 = Path(dir1).expanduser().resolve()
            for dir2 in managed_list[i+1:]:
                p2 = Path(dir2).expanduser().resolve()
                try:
                    if p1 == p2:
                        warnings.append(f"Duplicate managed directories: {dir1} and {dir2} resolve to same path")
                except:
                    pass

        return {
            "issues": issues,
            "warnings": warnings,
            "has_issues": len(issues) > 0,
            "has_warnings": len(warnings) > 0
        }

    @staticmethod
    def check_path(config: dict, path_str: str) -> dict:
        """Check if a path would be monitored and calculate its priority."""
        from .priority import calculate_priority

        monitor_config = config.get("monitor", {})
        include_paths = monitor_config.get("include_paths", [])
        exclude_paths = monitor_config.get("exclude_paths", [])
        ignore_dirnames = monitor_config.get("ignore_dirnames", [])
        ignore_globs = monitor_config.get("ignore_globs", [])
        managed_dirs = monitor_config.get("managed_directories", {})
        priority_config = monitor_config.get("priority", {})

        # Resolve path
        test_path = Path(path_str).expanduser().resolve()

        # Build decision chain
        decisions = []
        is_monitored = True
        reason = None
        priority = None

        # Step 1: Check if path exists
        path_exists = test_path.exists()
        decisions.append({
            "symbol": "✓" if path_exists else "⚠",
            "message": f"Path exists: {test_path}" if path_exists else f"Path does not exist (checking as if it did): {test_path}"
        })

        # Step 2: Check include_paths
        included = False
        for include_path in include_paths:
            include_resolved = Path(include_path).expanduser().resolve()
            try:
                test_path.relative_to(include_resolved)
                included = True
                decisions.append({"symbol": "✓", "message": f"Matches include_paths: {include_path}"})
                break
            except ValueError:
                continue

        if not included:
            is_monitored = False
            reason = "Not under any include_paths"
            decisions.append({"symbol": "✗", "message": reason})
            return {
                "path": str(test_path),
                "is_monitored": is_monitored,
                "reason": reason,
                "priority": None,
                "decisions": decisions
            }

        # Step 3: Check exclude_paths
        for exclude_path in exclude_paths:
            exclude_resolved = Path(exclude_path).expanduser().resolve()
            try:
                test_path.relative_to(exclude_resolved)
                is_monitored = False
                reason = f"Matched by exclude_paths: {exclude_path}"
                decisions.append({"symbol": "✗", "message": reason})
                return {
                    "path": str(test_path),
                    "is_monitored": is_monitored,
                    "reason": reason,
                    "priority": None,
                    "decisions": decisions
                }
            except ValueError:
                continue

        decisions.append({"symbol": "✓", "message": "Not in any exclude_paths"})

        # Step 4: Check ignore_dirnames
        for part in test_path.parts:
            if part in ignore_dirnames:
                is_monitored = False
                reason = f"Contains ignored dirname: {part}"
                decisions.append({"symbol": "✗", "message": reason})
                return {
                    "path": str(test_path),
                    "is_monitored": is_monitored,
                    "reason": reason,
                    "priority": None,
                    "decisions": decisions
                }

        decisions.append({"symbol": "✓", "message": "No ignored dirnames in path"})

        # Step 5: Check ignore_globs
        for glob_pattern in ignore_globs:
            if fnmatch.fnmatch(str(test_path), glob_pattern) or \
               fnmatch.fnmatch(test_path.name, glob_pattern):
                is_monitored = False
                reason = f"Matched by ignore_globs: {glob_pattern}"
                decisions.append({"symbol": "✗", "message": reason})
                return {
                    "path": str(test_path),
                    "is_monitored": is_monitored,
                    "reason": reason,
                    "priority": None,
                    "decisions": decisions
                }

        decisions.append({"symbol": "✓", "message": "Not matched by any ignore_globs"})

        # Step 6: Calculate priority
        try:
            priority = calculate_priority(test_path, managed_dirs, priority_config)
            decisions.append({"symbol": "✓", "message": f"Priority calculated: {priority}"})
        except Exception as e:
            priority = None
            decisions.append({"symbol": "⚠", "message": f"Could not calculate priority: {e}"})

        return {
            "path": str(test_path),
            "is_monitored": is_monitored,
            "reason": "Would be monitored",
            "priority": priority,
            "decisions": decisions
        }
