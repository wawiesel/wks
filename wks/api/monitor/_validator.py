"""API-local monitor validation helpers."""

from __future__ import annotations

from pathlib import Path

from .MonitorRules import MonitorRules
from ._ConfigValidationResult import _ConfigValidationResult
from ._PriorityDirectoryInfo import _PriorityDirectoryInfo


def _validator(cfg) -> _ConfigValidationResult:
    """Validate monitor config and return ConfigValidationResult.

    Structural validation is provided by the Pydantic MonitorConfig; this adds
    rule-based checks (managed directory validity) and aggregates issues.
    """
    rules = MonitorRules.from_config(cfg)

    managed_validation: dict[str, _PriorityDirectoryInfo] = {}
    issues: list[str] = []

    for path, priority in cfg.managed_directories.items():
        managed_resolved = Path(path).expanduser().resolve()
        allowed, trace = rules.explain(managed_resolved)
        err = None if allowed else (trace[-1] if trace else "Excluded by monitor rules")
        managed_validation[path] = _PriorityDirectoryInfo(priority=priority, valid=allowed, error=err)
        if err:
            issues.append(f"Managed directory invalid: {path} ({err})")

    return _ConfigValidationResult(
        issues=issues,
        redundancies=[],
        priority_directories=managed_validation,
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
