"""Diff engines for comparing files."""

import subprocess
from abc import ABC, abstractmethod
from pathlib import Path

try:
    import bsdiff4

    BSDIFF4_AVAILABLE = True
except ImportError:
    BSDIFF4_AVAILABLE = False
    bsdiff4 = None


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
    """Binary diff engine using bsdiff4 Python package."""

    def diff(self, file1: Path, file2: Path, options: dict) -> str:  # noqa: ARG002
        """Compute binary diff using bsdiff4.

        Args:
            file1: First file path
            file2: Second file path
            options: Options (currently unused for binary diff)

        Returns:
            Diff output (patch info or binary patch size)

        Raises:
            RuntimeError: If bsdiff4 is not available or diff operation fails
        """
        if not BSDIFF4_AVAILABLE:
            raise RuntimeError("bsdiff4 package is required for binary diff. Install with: pip install bsdiff4")

        # Read file contents
        try:
            old_data = file1.read_bytes()
            new_data = file2.read_bytes()
        except Exception as exc:
            raise RuntimeError(f"Failed to read files: {exc}") from exc

        # Check if files are identical
        if old_data == new_data:
            return "Files are identical (binary comparison)"

        # Generate binary patch
        try:
            patch = bsdiff4.diff(old_data, new_data)
            patch_size = len(patch)

            size1 = len(old_data)
            size2 = len(new_data)

            # Return informative diff summary
            return (
                f"Binary diff (bsdiff4 patch):\n"
                f"  {file1.name}: {size1} bytes\n"
                f"  {file2.name}: {size2} bytes\n"
                f"  Patch size: {patch_size} bytes\n"
                f"  Compression ratio: {patch_size / max(size1, size2) * 100:.1f}%"
            )
        except Exception as exc:
            raise RuntimeError(f"bsdiff4 diff operation failed: {exc}") from exc


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
                check=False,  # diff returns 1 for differences, which is OK
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
            with file_path.open("rb") as f:
                chunk = f.read(8192)

            # Check for null bytes (binary indicator)
            if b"\x00" in chunk:
                return False

            # Try to decode as UTF-8
            try:
                chunk.decode("utf-8")
                return True
            except UnicodeDecodeError:
                # Try ASCII
                try:
                    chunk.decode("ascii")
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


def get_engine(name: str) -> DiffEngine | None:
    """Get diff engine by name.

    Args:
        name: Engine name (e.g., "bsdiff3", "myers")

    Returns:
        Engine instance or None if not found
    """
    return ENGINES.get(name)
