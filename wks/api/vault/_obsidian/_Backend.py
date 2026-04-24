from __future__ import annotations

import platform
import re
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
    def __init__(self, vault_config: VaultConfig):
        from wks.api.config.normalize_path import normalize_path

        if not vault_config.base_dir:
            raise ValueError("vault.base_dir is required")

        self._vault_path = normalize_path(vault_config.base_dir)
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
        broken: list[Path] = []
        if not self._links_dir.exists():
            return broken
        for link in self._links_dir.rglob("*"):
            if link.is_symlink() and not link.exists():
                broken.append(link)
        return broken

    def resolve_link(self, target: str) -> LinkMetadata:
        target = target.strip()
        for predicate, resolver in self.resolvers:
            if predicate(target):
                return resolver(target)
        return self._resolve_vault_note(target)

    def _is_symlink(self, target: str) -> bool:
        return target.startswith("_links/")

    def _is_attachment(self, target: str) -> bool:
        return target.startswith("_") and not target.startswith("_links/")

    def _is_external_url(self, target: str) -> bool:
        return "://" in target

    def _resolve_symlink(self, target: str) -> LinkMetadata:
        rel = target[len("_links/") :]
        symlink_path = self.links_dir / rel

        if not symlink_path.exists():
            return self._resolve_vault_note(target, status=STATUS_MISSING_SYMLINK)

        try:
            resolved = symlink_path.resolve(strict=False)
        except (OSError, ValueError, RuntimeError):
            resolved = symlink_path

        resolved_exists = resolved.exists()
        status = STATUS_MISSING_TARGET if not resolved_exists else STATUS_OK

        try:
            from wks.api.config.URI import URI

            target_uri = str(URI.from_path(resolved))
        except (ValueError, OSError, ImportError):
            target_uri = f"file://{resolved}"

        return LinkMetadata(
            target_uri=target_uri,
            status=status,
        )

    def _resolve_attachment(self, target: str) -> LinkMetadata:
        abs_path = self.vault_path / target
        target_uri = f"vault:///{target}"
        return LinkMetadata(
            target_uri=target_uri,
            status=STATUS_OK if abs_path.exists() else STATUS_MISSING_TARGET,
        )

    def _resolve_external_url(self, target: str) -> LinkMetadata:
        return LinkMetadata(
            target_uri=target,
            status=STATUS_OK,
        )

    def _resolve_vault_note(self, target: str, status: str = STATUS_OK) -> LinkMetadata:
        note_target = target
        if not note_target.endswith(".md") and "." not in note_target:
            note_target += ".md"

        abs_path = self.vault_path / note_target

        target_status = status
        if target_status == STATUS_OK and not abs_path.exists():
            target_status = STATUS_MISSING_TARGET

        target_uri = f"vault:///{note_target}"
        return LinkMetadata(
            target_uri=target_uri,
            status=target_status,
        )

    def update_link_for_move(self, old_path: Path, new_path: Path) -> tuple[str, str] | None:
        old_rel_posix = str(old_path).lstrip("/")
        old_symlink = self._links_dir / self.machine / old_rel_posix

        if not old_symlink.is_symlink():
            return None

        new_rel_posix = str(new_path).lstrip("/")
        new_symlink = self._links_dir / self.machine / new_rel_posix

        new_symlink.parent.mkdir(parents=True, exist_ok=True)
        new_symlink.symlink_to(new_path)

        old_symlink.unlink()

        machine_dir = self._links_dir / self.machine
        parent = old_symlink.parent
        while parent != machine_dir and parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent

        old_vault_rel = str(old_symlink.relative_to(self._vault_path))
        new_vault_rel = str(new_symlink.relative_to(self._vault_path))
        return (old_vault_rel, new_vault_rel)

    def rewrite_wiki_links(self, old_target: str, new_target: str) -> int:
        pattern = re.compile(r"(!?\[\[)" + re.escape(old_target) + r"(\|[^\]]*)?(\]\])")
        replacement = rf"\g<1>{new_target}\g<2>\g<3>"

        count = 0
        for md_path in self.iter_markdown_files():
            try:
                text = md_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            new_text = pattern.sub(replacement, text)
            if new_text != text:
                md_path.write_text(new_text, encoding="utf-8")
                count += 1
        return count

    def update_edges_for_move(
        self,
        old_path: Path,
        new_path: Path,
        old_vault_rel: str,
        new_vault_rel: str,
    ) -> int:
        from wks.api.config.URI import URI
        from wks.api.config.WKSConfig import WKSConfig
        from wks.api.database.Database import Database

        config = WKSConfig.load()

        old_file_uri = str(URI.from_path(old_path))
        new_file_uri = str(URI.from_path(new_path))
        old_vault_uri = f"vault:///{old_vault_rel}"
        new_vault_uri = f"vault:///{new_vault_rel}"

        updated = 0
        with Database(config.database, "edges") as db:
            updated += db.update_many(
                {"to_local_uri": old_file_uri},
                {"$set": {"to_local_uri": new_file_uri}},
            )
            updated += db.update_many(
                {"to_local_uri": old_vault_uri},
                {"$set": {"to_local_uri": new_vault_uri}},
            )
        return updated
