"""Abstract base parser for link extraction."""

from abc import ABC, abstractmethod
from collections.abc import Iterator

from .LinkRef import LinkRef


class BaseParser(ABC):
    """Abstract interface for file parsers."""

    @abstractmethod
    def parse(self, text: str) -> Iterator[LinkRef]:
        """Parse text and yield found links."""
        pass
