"""Transform engine base class."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class TransformEngine(ABC):
    """Base class for transform engines."""

    @abstractmethod
    def transform(self, input_path: Path, output_path: Path, options: dict[str, Any]) -> None:
        """Transform file from input to output.

        Args:
            input_path: Source file path
            output_path: Destination file path
            options: Engine-specific options

        Raises:
            RuntimeError: If transform fails
        """
        pass

    @abstractmethod
    def get_extension(self, options: dict[str, Any]) -> str:
        """Get output file extension for this engine.

        Args:
            options: Engine-specific options

        Returns:
            File extension (e.g., "md", "txt")
        """
        pass

    def compute_options_hash(self, options: dict[str, Any]) -> str:
        """Compute hash of options for cache key.

        Args:
            options: Engine-specific options

        Returns:
            SHA-256 hash of options
        """
        import hashlib

        options_str = str(sorted(options.items()))
        return hashlib.sha256(options_str.encode()).hexdigest()[:16]
