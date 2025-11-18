"""Monitor list and managed directory operations."""

from pathlib import Path
from typing import Dict, Optional

from .status import ListOperationResult
from .validator import MonitorValidator


def _canonicalize_path(path_str: str) -> str:
    """Normalize a path string for comparison."""
    path_obj = Path(path_str).expanduser()
    try:
        return str(path_obj.resolve(strict=False))
    except Exception:
        return str(path_obj)


def _find_matching_path_key(path_map: Dict[str, any], candidate: str) -> Optional[str]:
    """Find the key in a path map that canonically matches candidate."""
    candidate_norm = _canonicalize_path(candidate)
    for key in path_map.keys():
        if _canonicalize_path(key) == candidate_norm:
            return key
    return None


class MonitorOperations:
    """Operations for modifying monitor configuration."""

    @staticmethod
    def add_to_list(config_dict: dict, list_name: str, value: str, resolve_path: bool = True) -> ListOperationResult:
        """Add value to a monitor config list.

        Args:
            config_dict: Configuration dictionary (will be modified)
            list_name: Name of list to modify
            value: Value to add
            resolve_path: Whether to resolve paths (for include/exclude_paths)

        Returns:
            ListOperationResult with success status and message
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
            ListOperationResult with success status and message
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
