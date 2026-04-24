from abc import ABC, abstractmethod
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .LinkMetadata import LinkMetadata


class _AbstractBackend(ABC):
    @property
    @abstractmethod
    def vault_path(self) -> Path:
        pass

    @abstractmethod
    def resolve_link(self, target: str) -> "LinkMetadata":
        pass

    @property
    @abstractmethod
    def links_dir(self) -> Path:
        pass

    @abstractmethod
    def iter_markdown_files(self) -> Iterator[Path]:
        pass
