from abc import ABC, abstractmethod
from collections.abc import Iterator

from .LinkRef import LinkRef


class BaseParser(ABC):
    name: str = "unknown"

    @abstractmethod
    def parse(self, text: str) -> Iterator[LinkRef]:
        pass
