"""Binary diff engine."""

from pathlib import Path

from .DiffEngine import DiffEngine

try:
    import bsdiff4

    BSDIFF4_AVAILABLE = True
except ImportError:
    BSDIFF4_AVAILABLE = False
    bsdiff4 = None


class Bsdiff4Engine(DiffEngine):
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

        try:
            old_data = file1.read_bytes()
            new_data = file2.read_bytes()
        except Exception as exc:
            raise RuntimeError(f"Failed to read files: {exc}") from exc

        if old_data == new_data:
            return "Files are identical (binary comparison)"

        try:
            if bsdiff4 is None:
                raise RuntimeError("bsdiff4 is None despite availability check")
            patch = bsdiff4.diff(old_data, new_data)
            patch_size = len(patch)

            size1 = len(old_data)
            size2 = len(new_data)

            return (
                "Binary diff (bsdiff4 patch):\n"
                f"  {file1.name}: {size1} bytes\n"
                f"  {file2.name}: {size2} bytes\n"
                f"  Patch size: {patch_size} bytes\n"
                f"  Compression ratio: {patch_size / max(size1, size2) * 100:.1f}%"
            )
        except Exception as exc:
            raise RuntimeError(f"bsdiff4 diff operation failed: {exc}") from exc
