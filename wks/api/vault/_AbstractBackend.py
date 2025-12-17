"""Abstract base class for vault implementations."""

from abc import ABC, abstractmethod
from collections.abc import Iterator
from pathlib import Path


class _AbstractBackend(ABC):
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

    # Methods needed by indexer/controller
