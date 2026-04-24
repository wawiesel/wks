from abc import ABC, abstractmethod
from pathlib import Path


class DiffEngine(ABC):
    @abstractmethod
    def diff(self, file1: Path, file2: Path, options: dict) -> str:
        pass
