"""
Lean Obsidian vault integration for WKS.

Implements _AbstractVault for Obsidian-style vaults with symlink-based external file linking.
"""

from __future__ import annotations

import contextlib
import platform
from collections.abc import Iterator
from pathlib import Path

from ._AbstractVault import _AbstractVault


class ObsidianVault(_AbstractVault):
    """Obsidian vault implementation for link maintenance."""

    def __init__(self, vault_path: Path, *, machine_name: str | None = None):
        self._vault_path = Path(vault_path)
        self.machine = (machine_name or platform.node().split(".")[0]).strip()
        self._links_dir = self._vault_path / "_links"

    @property
    def vault_path(self) -> Path:
        return self._vault_path

    @property
    def links_dir(self) -> Path:
        return self._links_dir

    def _link_rel_for_source(self, source_file: Path, preserve_structure: bool = True) -> str:
        if preserve_structure:
            try:
                relative = source_file.resolve().relative_to(Path("/"))
                return f"_links/{self.machine}/{relative.as_posix()}"
            except Exception:
                return f"_links/{self.machine}/{source_file.name}"
        return f"_links/{self.machine}/{source_file.name}"

    def link_file(self, source_file: Path, preserve_structure: bool = True) -> Path | None:
        if not source_file.exists():
            return None

        if preserve_structure:
            try:
                relative = source_file.resolve().relative_to(Path("/"))
                link_path = self._links_dir / self.machine / relative
            except ValueError:
                link_path = self._links_dir / self.machine / source_file.name
        else:
            link_path = self._links_dir / self.machine / source_file.name

        link_path.parent.mkdir(parents=True, exist_ok=True)
        if not link_path.exists():
            link_path.symlink_to(source_file)
        return link_path

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

    def cleanup_broken_links(self) -> int:
        """Remove broken symlinks from the _links directory."""
        broken = self.find_broken_links()
        for link in broken:
            with contextlib.suppress(OSError, PermissionError):
                link.unlink()
        return len(broken)
