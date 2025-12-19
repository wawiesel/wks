"""Abstract base parser for link extraction."""

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass


@dataclass
class LinkRef:
    """A reference to a link found in a file."""

    line_number: int
    column_number: int
    raw_target: str
    link_type: str  # "wikilink", "url", "image", "reference", etc.
    alias: str = ""
    is_embed: bool = False


class BaseParser(ABC):
    """Abstract interface for file parsers."""

    @abstractmethod
    def parse(self, text: str) -> Iterator[LinkRef]:
        """Parse text and yield found links."""
        pass
