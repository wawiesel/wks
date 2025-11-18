"""Validation logic for monitor configuration."""

import fnmatch
from pathlib import Path
from typing import List, Optional, Tuple

from ..monitor_rules import MonitorRules


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
