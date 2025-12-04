"""Git-based vault change detection for efficient incremental scanning."""

from __future__ import annotations

__all__ = [
    "GitVaultWatcher",
    "VaultChanges",
]

import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class VaultChanges:
    """Changed files detected in vault repository."""

    modified: list[Path] = field(default_factory=list)
    added: list[Path] = field(default_factory=list)
    deleted: list[Path] = field(default_factory=list)
    renamed: list[tuple[Path, Path]] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        """Check if any changes detected."""
        return bool(self.modified or self.added or self.deleted or self.renamed)

    @property
    def all_affected_files(self) -> set[Path]:
        """Get all files affected by changes (for scanning)."""
        files = set()
        files.update(self.modified)
        files.update(self.added)
        # Include destination paths from renames
        files.update(dest for _, dest in self.renamed)
        return files


class GitVaultWatcher:
    """Watch vault for changes using git."""

    def __init__(self, vault_path: Path):
        """
        Initialize git watcher.

        Args:
            vault_path: Path to vault root directory (must be git repo)

        Raises:
            RuntimeError: If vault is not a git repository
        """
        self.vault_path = vault_path.resolve()

        # Verify it's a git repo
        if not self._is_git_repo():
            raise RuntimeError(f"Vault is not a git repository: {self.vault_path}")

    def _is_git_repo(self) -> bool:
        """Check if vault is a git repository."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=self.vault_path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception as exc:
            logger.debug(f"Git check failed: {exc}")
            return False

    def _parse_status_line(self, line: str, changes: VaultChanges) -> None:
        """Parse a single line from git status --porcelain output.

        Args:
            line: Single line from git status output
            changes: VaultChanges object to update
        """
        if not line:
            return

        # Format: "XY path" where X=index status, Y=worktree status
        # See: https://git-scm.com/docs/git-status#_short_format
        status = line[:2]
        path_str = line[3:]

        # Handle renames (format: "R  old -> new")
        if "R" in status:
            if " -> " in path_str:
                old_str, new_str = path_str.split(" -> ", 1)
                old_path = self.vault_path / old_str.strip()
                new_path = self.vault_path / new_str.strip()

                if new_path.suffix == ".md":
                    changes.renamed.append((old_path, new_path))
            return

        # Regular file changes
        path = self.vault_path / path_str.strip()

        # Only track markdown files
        if path.suffix != ".md":
            return

        # Modified (M), modified in index (AM, MM, etc.)
        if "M" in status:
            changes.modified.append(path)
        # Added (A), untracked (??)
        elif "A" in status or "?" in status:
            changes.added.append(path)
        # Deleted (D)
        elif "D" in status:
            changes.deleted.append(path)

    def get_changes(self) -> VaultChanges:
        """Get all uncommitted changes in vault.

        Returns:
            VaultChanges with lists of modified/added/deleted/renamed files

        Notes:
            - Uses `git status --porcelain` to detect changes
            - Only returns markdown files (.md)
            - Paths are absolute and resolved
        """
        changes = VaultChanges()

        try:
            # Run git status --porcelain to get change status
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.vault_path,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                logger.error(f"git status failed: {result.stderr}")
                return changes

            # Parse output
            for line in result.stdout.splitlines():
                self._parse_status_line(line, changes)

        except subprocess.TimeoutExpired:
            logger.error("git status command timed out")
        except Exception as exc:
            logger.error(f"Failed to get git changes: {exc}")

        return changes

    def _parse_diff_line(self, line: str, changes: VaultChanges) -> None:
        """Parse a single line from git diff --name-status output.

        Args:
            line: Single line from git diff output
            changes: VaultChanges object to update
        """
        if not line:
            return

        parts = line.split("\t", 1)
        if len(parts) != 2:
            return

        status, path_str = parts
        path = self.vault_path / path_str.strip()

        # Only track markdown files
        if path.suffix != ".md":
            return

        if status.startswith("M"):
            changes.modified.append(path)
        elif status.startswith("A"):
            changes.added.append(path)
        elif status.startswith("D"):
            changes.deleted.append(path)
        elif status.startswith("R") and len(parts) > 2:
            # Renamed files have format: "R100\told\tnew"
            old_path = self.vault_path / parts[1].strip()
            new_path = self.vault_path / parts[2].strip()
            if new_path.suffix == ".md":
                changes.renamed.append((old_path, new_path))

    def get_changed_since_commit(self, commit: str = "HEAD") -> VaultChanges:
        """Get changes since a specific commit.

        Args:
            commit: Git commit reference (default: HEAD)

        Returns:
            VaultChanges with modified/added/deleted files

        Notes:
            - Uses `git diff --name-status` to compare with commit
            - Useful for detecting changes since last successful scan
        """
        changes = VaultChanges()

        try:
            result = subprocess.run(
                ["git", "diff", "--name-status", commit],
                cwd=self.vault_path,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                logger.error(f"git diff failed: {result.stderr}")
                return changes

            for line in result.stdout.splitlines():
                self._parse_diff_line(line, changes)

        except subprocess.TimeoutExpired:
            logger.error("git diff command timed out")
        except Exception as exc:
            logger.error(f"Failed to get git diff: {exc}")

        return changes

    def has_uncommitted_changes(self) -> bool:
        """Check if vault has any uncommitted changes.

        Returns:
            True if there are uncommitted changes, False otherwise
        """
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.vault_path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            return bool(result.stdout.strip())
        except Exception as exc:
            logger.error(f"Failed to check git status: {exc}")
            return False
