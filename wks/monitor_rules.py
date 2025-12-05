"""Shared include/exclude evaluation logic for monitor paths."""

from __future__ import annotations

import fnmatch
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING

from .constants import WKS_DOT_DIRS

if TYPE_CHECKING:  # pragma: no cover - for type checking only
    from .api.monitor.MonitorConfig import MonitorConfig


def _matches_glob(patterns: list[str], path_obj: Path) -> bool:
    if not patterns:
        return False
    path_str = path_obj.as_posix()
    name = path_obj.name
    for pattern in patterns:
        if not pattern:
            continue
        try:
            if fnmatch.fnmatchcase(path_str, pattern) or fnmatch.fnmatchcase(name, pattern):
                return True
        except Exception:
            continue
    return False


class MonitorRules:
    """Evaluate include/exclude rules for filesystem monitoring."""

    def __init__(
        self,
        *,
        include_paths: Iterable[str],
        exclude_paths: Iterable[str],
        include_dirnames: Iterable[str],
        exclude_dirnames: Iterable[str],
        include_globs: Iterable[str],
        exclude_globs: Iterable[str],
    ):
        self.include_roots = [Path(p).expanduser().resolve() for p in include_paths]
        self.exclude_roots = [Path(p).expanduser().resolve() for p in exclude_paths]
        self.include_root_set = set(self.include_roots)
        self.exclude_root_set = set(self.exclude_roots)
        self.include_dirnames = self._normalize_dirnames(include_dirnames)
        self.exclude_dirnames = self._normalize_dirnames(exclude_dirnames)
        self.exclude_dirnames.update(WKS_DOT_DIRS)
        self.include_globs = self._normalize_globs(include_globs)
        self.exclude_globs = self._normalize_globs(exclude_globs)

    @staticmethod
    def _normalize_dirnames(dirnames: Iterable[str]) -> set[str]:
        """Normalize directory names by stripping whitespace and filtering empty values.

        Args:
            dirnames: Iterable of directory name strings

        Returns:
            Set of normalized directory names
        """
        return {d.strip() for d in dirnames if d and d.strip()}

    @staticmethod
    def _normalize_globs(globs: Iterable[str]) -> list[str]:
        """Normalize glob patterns by stripping whitespace and filtering empty values.

        Args:
            globs: Iterable of glob pattern strings

        Returns:
            List of normalized glob patterns
        """
        return [g.strip() for g in globs if g]

    @classmethod
    def from_config(cls, cfg: MonitorConfig) -> MonitorRules:
        """Convenience constructor from MonitorConfig."""
        return cls(
            include_paths=cfg.include_paths,
            exclude_paths=cfg.exclude_paths,
            include_dirnames=cfg.include_dirnames,
            exclude_dirnames=cfg.exclude_dirnames,
            include_globs=cfg.include_globs,
            exclude_globs=cfg.exclude_globs,
        )

    def allows(self, path: Path) -> bool:
        allowed, _ = self.explain(path)
        return allowed

    def explain(self, path: Path) -> tuple[bool, list[str]]:
        trace: list[str] = []
        resolved = path.expanduser().resolve()

        root_allowed, root_reason = self._evaluate_roots(resolved)
        trace.append(root_reason)
        if not root_allowed:
            return False, trace

        parent = resolved.parent.name if resolved.parent != resolved else ""
        excluded = False
        if parent in self.exclude_dirnames:
            trace.append(f"Parent dir '{parent}' excluded")
            excluded = True

        if _matches_glob(self.exclude_globs, resolved):
            trace.append("Excluded by glob pattern")
            excluded = True

        if excluded:
            if parent in self.include_dirnames:
                trace.append(f"Parent dir '{parent}' override")
                return True, trace
            if _matches_glob(self.include_globs, resolved):
                trace.append("Included by glob override")
                return True, trace
            return False, trace

        # Not excluded, no override needed
        return True, trace

    def _evaluate_roots(self, path: Path) -> tuple[bool, str]:
        cur = path
        while True:
            if cur in self.exclude_root_set:
                return False, f"Excluded by root {cur}"
            if cur in self.include_root_set:
                return True, f"Included by root {cur}"
            parent = cur.parent
            if parent == cur:
                if self.include_root_set:
                    return False, "Outside include_paths"
                return False, "No include_paths defined; default exclude"
            cur = parent
