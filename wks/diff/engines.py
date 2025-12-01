"""Diff engines for comparing files."""

import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


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


class Bsdiff3Engine(DiffEngine):
    """Binary diff engine using bsdiff3."""

    def diff(self, file1: Path, file2: Path, options: dict) -> str:
        """Compute binary diff using bsdiff3.

        Args:
            file1: First file path
            file2: Second file path
            options: Options (currently unused for binary diff)

        Returns:
            Diff output (patch info)

        Raises:
            RuntimeError: If bsdiff3 command fails
        """
        # For now, return basic file comparison info
        # TODO: Implement actual bsdiff3 integration
        size1 = file1.stat().st_size
        size2 = file2.stat().st_size

        if file1.read_bytes() == file2.read_bytes():
            return "Files are identical (binary comparison)"

        return f"Files differ:\n  {file1.name}: {size1} bytes\n  {file2.name}: {size2} bytes"


class MyersEngine(DiffEngine):
    """Text diff engine using Myers algorithm (via standard diff)."""

    def diff(self, file1: Path, file2: Path, options: dict) -> str:
        """Compute text diff using Myers algorithm.

        Args:
            file1: First file path
            file2: Second file path
            options: Options (context_lines, etc.)

        Returns:
            Unified diff output

        Raises:
            ValueError: If files are not text
            RuntimeError: If diff command fails
        """
        # Check if files are text
        if not self._is_text_file(file1):
            raise ValueError(f"{file1} is not a text file or has unsupported encoding")
        if not self._is_text_file(file2):
            raise ValueError(f"{file2} is not a text file or has unsupported encoding")

        # Get context lines option
        context_lines = options.get("context_lines", 3)

        # Run diff command
        cmd = ["diff", f"-U{context_lines}", str(file1), str(file2)]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False  # diff returns 1 for differences, which is OK
            )

            # Return code 0 = no differences, 1 = differences found, 2+ = error
            if result.returncode >= 2:
                raise RuntimeError(f"diff command failed: {result.stderr}")

            if result.returncode == 0:
                return "Files are identical"

            return result.stdout

        except Exception as exc:
            if isinstance(exc, RuntimeError):
                raise
            raise RuntimeError(f"diff error: {exc}") from exc

    def _is_text_file(self, file_path: Path) -> bool:
        """Check if file is text with supported encoding.

        Args:
            file_path: Path to file

        Returns:
            True if file is text, False otherwise
        """
        try:
            # Read first chunk to check for binary content
            with open(file_path, 'rb') as f:
                chunk = f.read(8192)

            # Check for null bytes (binary indicator)
            if b'\x00' in chunk:
                return False

            # Try to decode as UTF-8
            try:
                chunk.decode('utf-8')
                return True
            except UnicodeDecodeError:
                # Try ASCII
                try:
                    chunk.decode('ascii')
                    return True
                except UnicodeDecodeError:
                    return False
        except Exception:
            return False


# Registry of available engines
ENGINES = {
    "bsdiff3": Bsdiff3Engine(),
    "myers": MyersEngine(),
    "unified": MyersEngine(),
}


def get_engine(name: str) -> Optional[DiffEngine]:
    """Get diff engine by name.

    Args:
        name: Engine name (e.g., "bsdiff3", "myers")

    Returns:
        Engine instance or None if not found
    """
    return ENGINES.get(name)
