"""Text diff engine (UNO: single class)."""

import subprocess
from pathlib import Path

from .DiffEngine import DiffEngine


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
