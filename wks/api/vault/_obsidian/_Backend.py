"""
Lean Obsidian vault integration for WKS.

Implements _AbstractVault for Obsidian-style vaults with symlink-based external file linking.
"""

from __future__ import annotations

import platform
from collections.abc import Iterator
from pathlib import Path

from .._AbstractBackend import _AbstractBackend
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

    @property
    def vault_path(self) -> Path:
        return self._vault_path

    @property
    def links_dir(self) -> Path:
        return self._links_dir

    def iter_markdown_files(self) -> Iterator[Path]:
        """Iterate all markdown files in the vault (excludes _links/)."""
        for md in self._vault_path.rglob("*.md"):
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
