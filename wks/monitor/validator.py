"""Validation logic for monitor configuration."""

import fnmatch
from pathlib import Path

from ..monitor_rules import MonitorRules
from ..monitor.status import ConfigValidationResult, ManagedDirectoryInfo


class MonitorValidator:
    """Validation logic for monitor configuration."""

    @staticmethod
    def status_symbol(error_msg: str | None, is_valid: bool = True) -> str:
        """Convert validation result to colored status symbol."""
        return "[green]✓[/]" if not error_msg else "[yellow]⚠[/]" if is_valid else "[red]✗[/]"

    @staticmethod
    def validate_dirname_entry(dirname: str) -> tuple[bool, str | None]:
        """Validate include/exclude dirname entries."""
        if not dirname or not dirname.strip():
            return False, "Directory name cannot be empty"
        if any(ch in dirname for ch in "*?[]"):
            return False, "Directory names cannot contain wildcard characters (*, ?, [)"
        if "/" in dirname or "\\" in dirname:
            return False, "Directory names cannot contain path separators"
        return True, None

    @staticmethod
    def dirname_redundancy(dirname: str, related_globs: list[str], relation: str) -> str | None:
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
    def validate_glob_pattern(pattern: str) -> tuple[bool, str | None]:
        """Validate glob syntax for include/exclude lists."""
        if not pattern or not pattern.strip():
            return False, "Glob pattern cannot be empty"
        try:
            fnmatch.fnmatch("test", pattern)
            return True, None
        except Exception as e:
            return False, f"Invalid glob syntax: {e!s}"

    @staticmethod
    def validate_managed_directory(managed_path: str, rules: MonitorRules) -> tuple[bool, str | None]:
        """Validate that a managed_directory would actually be monitored."""
        managed_resolved = Path(managed_path).expanduser().resolve()

        wks_home = Path("~/.wks").expanduser().resolve()
        if managed_resolved == wks_home or str(managed_resolved).startswith(str(wks_home) + "/"):
            return False, "In WKS home directory (automatically ignored)"

        if ".wks" in managed_resolved.parts:
            return False, "Contains .wks directory (automatically ignored)"

        allowed, trace = rules.explain(managed_resolved)
        if allowed:
            return True, None

        if trace:
            return False, trace[-1]
        return False, "Excluded by monitor rules"

    @staticmethod
    def validate_config(cfg) -> ConfigValidationResult:
        """Basic config validation producing ConfigValidationResult."""
        rules = MonitorRules.from_config(cfg)

        managed_validation = {}
        for path, priority in cfg.managed_directories.items():
            is_valid, error_msg = MonitorValidator.validate_managed_directory(path, rules)
            managed_validation[path] = ManagedDirectoryInfo(priority=priority, valid=is_valid, error=error_msg)

        return ConfigValidationResult(
            issues=[],
            redundancies=[],
            managed_directories=managed_validation,
            include_paths=list(cfg.include_paths),
            exclude_paths=list(cfg.exclude_paths),
            include_dirnames=list(cfg.include_dirnames),
            exclude_dirnames=list(cfg.exclude_dirnames),
            include_globs=list(cfg.include_globs),
            exclude_globs=list(cfg.exclude_globs),
            include_dirname_validation={},
            exclude_dirname_validation={},
            include_glob_validation={},
            exclude_glob_validation={},
        )
