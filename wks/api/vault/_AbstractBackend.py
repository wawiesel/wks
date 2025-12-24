"""Abstract base class for vault implementations."""

from abc import ABC, abstractmethod
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .LinkMetadata import LinkMetadata


class _AbstractBackend(ABC):
    """Abstract interface for a Vault implementation."""

    @property
    @abstractmethod
    def vault_path(self) -> Path:
        """Root directory of the vault."""
        pass

    @abstractmethod
    def resolve_link(self, target: str) -> "LinkMetadata":
        """Resolve a wiki link target to metadata."""
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

    # Methods needed by indexer/controller
