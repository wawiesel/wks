"""
Lean Obsidian vault integration for WKS.

Implements _AbstractVault for Obsidian-style vaults with symlink-based external file linking.
"""

from __future__ import annotations

import platform
from collections.abc import Callable, Generator
from pathlib import Path

from .._AbstractBackend import _AbstractBackend
from .._constants import (
    STATUS_MISSING_SYMLINK,
    STATUS_MISSING_TARGET,
    STATUS_OK,
)
from ..LinkMetadata import LinkMetadata
from ..VaultConfig import VaultConfig


class _Backend(_AbstractBackend):
    """Obsidian vault implementation for link maintenance."""

    def __init__(self, vault_config: VaultConfig):
        from wks.utils.expand_path import expand_path

        if not vault_config.base_dir:
            raise ValueError("vault.base_dir is required")

        self._vault_path = expand_path(vault_config.base_dir)
        self.machine = (platform.node().split(".")[0]).strip()
        self._links_dir = self._vault_path / "_links"

        self.resolvers: list[tuple[Callable[[str], bool], Callable[[str], LinkMetadata]]] = [
            (self._is_symlink, self._resolve_symlink),
            (self._is_attachment, self._resolve_attachment),
            (self._is_external_url, self._resolve_external_url),
        ]

    @property
    def vault_path(self) -> Path:
        return self._vault_path

    @property
    def links_dir(self) -> Path:
        return self._links_dir

    def iter_markdown_files(self) -> Generator[Path, None, None]:
        """Iterate all markdown files in the vault (excludes _links/)."""
        for md in self._vault_path.rglob("*.md"):
            if not md.is_file():
                continue
            try:
                rel_to_vault = md.relative_to(self._vault_path)
                if rel_to_vault.parts[0] == "_links":
                    continue
            except (ValueError, IndexError):
                continue
            if ".wks" in md.parts:
                continue
            try:
                yield md
            except (OSError, PermissionError):
                continue

    def find_broken_links(self) -> list[Path]:
        """Find all broken symlinks in the _links directory."""
        broken: list[Path] = []
        if not self._links_dir.exists():
            return broken
        for link in self._links_dir.rglob("*"):
            if link.is_symlink() and not link.exists():
                broken.append(link)
        return broken

    def resolve_link(self, target: str) -> LinkMetadata:
        """Resolve a wiki link target to metadata."""
        target = target.strip()
        for predicate, resolver in self.resolvers:
            if predicate(target):
                return resolver(target)
        return self._resolve_vault_note(target)

    # Predicates
    def _is_symlink(self, target: str) -> bool:
        return target.startswith("_links/")

    def _is_attachment(self, target: str) -> bool:
        return target.startswith("_") and not target.startswith("_links/")

    def _is_external_url(self, target: str) -> bool:
        return "://" in target

    # Resolvers
    def _resolve_symlink(self, target: str) -> LinkMetadata:
        """Resolve _links/ symlink target.

        Returns file:// URI for resolved symlink target, or vault:// fallback if missing.
        """
        rel = target[len("_links/") :]
        symlink_path = self.links_dir / rel

        if not symlink_path.exists():
            # Symlink doesn't exist - resolve as internal if it looks like one, or mark missing
            return self._resolve_vault_note(target, status=STATUS_MISSING_SYMLINK)

        try:
            resolved = symlink_path.resolve(strict=False)
        except (OSError, ValueError, RuntimeError):
            # OSError: Permission denied, file system issues
            # ValueError: Invalid path
            # RuntimeError: Symlink loop or too many levels
            resolved = symlink_path

        resolved_exists = resolved.exists()
        status = STATUS_MISSING_TARGET if not resolved_exists else STATUS_OK

        # Use path_to_uri for resolved filesystem path
        try:
            from wks.utils.path_to_uri import path_to_uri

            target_uri = path_to_uri(resolved)
        except (ValueError, OSError):
            # Fallback to absolute file path string if URI conversion fails
            target_uri = f"file://{resolved}"

        return LinkMetadata(
            target_uri=target_uri,
            status=status,
        )

    def _resolve_attachment(self, target: str) -> LinkMetadata:
        """Resolve vault attachment (files starting with _)."""
        abs_path = self.vault_path / target
        # Vault attachments use vault:/// URI
        target_uri = f"vault:///{target}"
        return LinkMetadata(
            target_uri=target_uri,
            status=STATUS_OK if abs_path.exists() else STATUS_MISSING_TARGET,
        )

    def _resolve_external_url(self, target: str) -> LinkMetadata:
        """Resolve external URL (contains ://)."""
        return LinkMetadata(
            target_uri=target,
            status=STATUS_OK,
        )

    def _resolve_vault_note(self, target: str, status: str = STATUS_OK) -> LinkMetadata:
        """Resolve as vault note (default case) using vault:/// URI."""
        # Append .md if not present and doesn't look like a file with extension
        note_target = target
        if not note_target.endswith(".md") and "." not in note_target:
            note_target += ".md"

        abs_path = self.vault_path / note_target

        target_status = status
        if target_status == STATUS_OK and not abs_path.exists():
            target_status = STATUS_MISSING_TARGET

        # Use vault:/// relative URI
        target_uri = f"vault:///{note_target}"
        return LinkMetadata(
            target_uri=target_uri,
            status=target_status,
        )
