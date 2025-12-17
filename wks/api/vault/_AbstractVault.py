"""Abstract base class for vault implementations."""

from abc import ABC, abstractmethod
from collections.abc import Iterator
from pathlib import Path


class _AbstractVault(ABC):
    """Abstract interface for a Vault implementation."""

    @property
    @abstractmethod
    def vault_path(self) -> Path:
        """Root directory of the vault."""
        pass

    @property
    @abstractmethod
    def links_dir(self) -> Path:
        """Directory where external links are stored."""
        pass

    @abstractmethod
    def iter_markdown_files(self) -> Iterator[Path]:
        """Iterate over all markdown files in the vault."""
        pass

    @abstractmethod
    def link_file(self, source_file: Path, preserve_structure: bool = True) -> Path | None:
        """Create a link (symlink) in the vault to an external file.

        Args:
            source_file: The external file to link.
            preserve_structure: If True, mirror the path structure in the links directory.

        Returns:
            The path to the created link/symlink, or None if failed/skipped.
        """
        pass

    # Methods needed by indexer/controller

    @abstractmethod
    def _link_rel_for_source(self, source_file: Path, preserve_structure: bool = True) -> str:
        """Calculate the relative path for a link to the source file.

        TODO: This probably shouldn't be private in the abstract interface if external components rely on it.
        For now, we keep the name to minimize refactoring churn, or we rename it to `get_link_relative_path`.
        """
        pass
