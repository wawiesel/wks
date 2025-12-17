"""Link resolution strategies for different target types."""

from __future__ import annotations

__all__ = ["_LinkMetadata", "_LinkResolver"]

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .._constants import (
    STATUS_LEGACY_LINK,
    STATUS_MISSING_SYMLINK,
    STATUS_MISSING_TARGET,
    STATUS_OK,
)


@dataclass(frozen=True)
class _LinkMetadata:
    """Metadata about a resolved link target.

    URI-first design: target_uri is the canonical identifier.
    Filesystem paths and target_kind can be derived from target_uri and other fields.
    """

    target_uri: str
    status: str

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary for backward compatibility."""
        return {
            "target_uri": self.target_uri,
            "status": self.status,
        }


class _LinkResolver:
    """Resolves different types of Obsidian wiki links."""

    def __init__(self, links_dir: Path):
        """Initialize link resolver with vault's _links directory.

        Args:
            links_dir: Path to the vault's _links directory
        """
        self.links_dir = links_dir
        self.resolvers: list[tuple[Callable[[str], bool], Callable[[str], _LinkMetadata]]] = [
            (self._is_legacy_links, self._resolve_legacy_links),
            (self._is_symlink, self._resolve_symlink),
            (self._is_attachment, self._resolve_attachment),
            (self._is_external_url, self._resolve_external_url),
            (self._is_legacy_path, self._resolve_legacy_path),
        ]

    def resolve(self, target: str) -> _LinkMetadata:
        """Resolve a wiki link target to metadata.

        Args:
            target: The link target string from [[target]]

        Returns:
            _LinkMetadata with target information
        """
        target = target.strip()
        for predicate, resolver in self.resolvers:
            if predicate(target):
                return resolver(target)
        return self._resolve_vault_note(target)

    # Predicates
    def _is_legacy_links(self, target: str) -> bool:
        return target.lower().startswith("links/")

    def _is_symlink(self, target: str) -> bool:
        return target.startswith("_links/")

    def _is_attachment(self, target: str) -> bool:
        return target.startswith("_") and not target.startswith("_links/")

    def _is_external_url(self, target: str) -> bool:
        return "://" in target

    def _is_legacy_path(self, target: str) -> bool:
        return target.startswith("/")

    # Resolvers
    def _resolve_legacy_links(self, target: str) -> _LinkMetadata:
        """Resolve legacy links/ prefix (deprecated)."""
        normalized = target[target.lower().index("links/") + len("links/") :]
        return _LinkMetadata(
            target_uri=f"legacy:///{normalized}",
            status=STATUS_LEGACY_LINK,
        )

    def _resolve_symlink(self, target: str) -> _LinkMetadata:
        """Resolve _links/ symlink target.

        Returns file:// URI for resolved symlink target, or vault:// fallback if missing.
        """
        rel = target[len("_links/") :]
        symlink_path = self.links_dir / rel

        if not symlink_path.exists():
            # Symlink doesn't exist - use vault:// fallback
            return _LinkMetadata(
                target_uri=f"vault:///{target}",
                status=STATUS_MISSING_SYMLINK,
            )

        try:
            resolved = symlink_path.resolve(strict=False)
        except (OSError, ValueError, RuntimeError):
            # OSError: Permission denied, file system issues
            # ValueError: Invalid path
            # RuntimeError: Symlink loop or too many levels
            resolved = symlink_path

        resolved_exists = resolved.exists()
        status = STATUS_MISSING_TARGET if not resolved_exists else STATUS_OK

        # Use file:// URI for resolved filesystem path
        try:
            target_uri = resolved.as_uri()
        except (ValueError, OSError):
            # Fallback to vault:// if URI conversion fails
            target_uri = f"vault:///{target}"

        return _LinkMetadata(
            target_uri=target_uri,
            status=status,
        )

    def _resolve_attachment(self, target: str) -> _LinkMetadata:
        """Resolve vault attachment (files starting with _)."""
        return _LinkMetadata(
            target_uri=f"vault:///{target}",
            status=STATUS_OK,
        )

    def _resolve_external_url(self, target: str) -> _LinkMetadata:
        """Resolve external URL (contains ://)."""
        return _LinkMetadata(
            target_uri=target,
            status=STATUS_OK,
        )

    def _resolve_legacy_path(self, target: str) -> _LinkMetadata:
        """Resolve legacy absolute path."""
        return _LinkMetadata(
            target_uri=f"legacy:///{target}",
            status=STATUS_LEGACY_LINK,
        )

    def _resolve_vault_note(self, target: str) -> _LinkMetadata:
        """Resolve as vault note (default case)."""
        return _LinkMetadata(
            target_uri=f"vault:///{target}",
            status=STATUS_OK,
        )
