"""Link resolver (UNO: single class)."""

from collections.abc import Callable
from pathlib import Path

from .._constants import (
    STATUS_MISSING_SYMLINK,
    STATUS_MISSING_TARGET,
    STATUS_OK,
)
from .LinkMetadata import LinkMetadata


class LinkResolver:
    """Resolves different types of Obsidian wiki links."""

    def __init__(self, vault_path: Path, links_dir: Path):
        """Initialize link resolver.

        Args:
            vault_path: Path to the vault root directory
            links_dir: Path to the vault's _links directory
        """
        self.vault_path = vault_path
        self.links_dir = links_dir
        self.resolvers: list[tuple[Callable[[str], bool], Callable[[str], LinkMetadata]]] = [
            (self._is_symlink, self._resolve_symlink),
            (self._is_attachment, self._resolve_attachment),
            (self._is_external_url, self._resolve_external_url),
        ]

    def resolve(self, target: str) -> LinkMetadata:
        """Resolve a wiki link target to metadata.

        Args:
            target: The link target string from [[target]]

        Returns:
            LinkMetadata with target information
        """
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
            from ....utils.path_to_uri import path_to_uri

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
