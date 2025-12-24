"""Base class for diff engines."""

from abc import ABC, abstractmethod
from pathlib import Path


class DiffEngine(ABC):
    """Base class for diff engines."""

    @abstractmethod
    def diff(self, file1: Path, file2: Path, options: dict) -> str:
        """Compute diff between two files.

        Args:
            file1: First file path
            file2: Second file path
            options: Engine-specific options

        Returns:
            Diff output as string

        Raises:
            ValueError: If files don't meet engine requirements
            RuntimeError: If diff operation fails
        """
        pass
