"""Diff controller with business logic."""

from pathlib import Path
from typing import Optional

from .engines import get_engine


class DiffController:
    """Business logic for diff operations."""

    def diff(
        self,
        file1: Path,
        file2: Path,
        engine_name: str,
        options: Optional[dict] = None
    ) -> str:
        """Compute diff between two files.

        Args:
            file1: First file path (or cache checksum)
            file2: Second file path (or cache checksum)
            engine_name: Diff engine name (e.g., "bdiff3", "myers")
            options: Engine-specific options

        Returns:
            Diff output as string

        Raises:
            ValueError: If files don't exist or engine not found
            RuntimeError: If diff operation fails
        """
        # Resolve paths
        file1 = Path(file1).resolve()
        file2 = Path(file2).resolve()

        if not file1.exists():
            raise ValueError(f"File not found: {file1}")

        if not file2.exists():
            raise ValueError(f"File not found: {file2}")

        # Get engine
        engine = get_engine(engine_name)
        if not engine:
            raise ValueError(f"Unknown engine: {engine_name}")

        # Perform diff
        options = options or {}
        return engine.diff(file1, file2, options)
