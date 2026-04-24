from abc import ABC, abstractmethod
from collections.abc import Generator
from pathlib import Path
from typing import Any


class _TransformEngine(ABC):
    @abstractmethod
    @abstractmethod
    def transform(
        self, input_path: Path, output_path: Path, options: dict[str, Any]
    ) -> Generator[str, None, list[str]]:
        pass

    @abstractmethod
    def get_extension(self, options: dict[str, Any]) -> str:
        pass

    def compute_options_hash(self, options: dict[str, Any]) -> str:
        import hashlib

        options_str = str(sorted(options.items()))
        return hashlib.sha256(options_str.encode()).hexdigest()[:16]
