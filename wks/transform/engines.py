"""Transform engines for converting binary to text."""

import hashlib
import subprocess
import tempfile
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
        options_str = str(sorted(options.items()))
        return hashlib.sha256(options_str.encode()).hexdigest()[:16]


class DoclingEngine(TransformEngine):
    """Docling transform engine for PDF, DOCX, PPTX."""

    def transform(self, input_path: Path, output_path: Path, options: dict[str, Any]) -> None:
        """Transform document using docling.

        Args:
            input_path: Source file path
            output_path: Destination file path
            options: Docling options (ocr, timeout_secs, max_chars, etc.)

        Raises:
            RuntimeError: If docling command fails
        """
        # Docling writes to an output directory, not stdout
        # Use temp directory and copy result
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_output = Path(temp_dir)

            cmd = ["docling", str(input_path), "--to", "md", "--output", str(temp_output)]

            # Add OCR flag if enabled
            if options.get("ocr", False):
                cmd.append("--ocr")

            # Set timeout
            timeout = options.get("timeout_secs", 30)

            try:
                subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=True)

                # Docling writes <input_stem>.md to output directory
                expected_output = temp_output / f"{input_path.stem}.md"

                if not expected_output.exists():
                    raise RuntimeError(f"Docling did not create expected output: {expected_output}")

                # Copy to final destination
                output_path.write_bytes(expected_output.read_bytes())

            except subprocess.TimeoutExpired as exc:
                raise RuntimeError(f"Docling timed out after {timeout}s") from exc
            except subprocess.CalledProcessError as exc:
                raise RuntimeError(f"Docling failed: {exc.stderr}") from exc
            except Exception as exc:
                raise RuntimeError(f"Docling error: {exc}") from exc

    def get_extension(self, options: dict[str, Any]) -> str:
        """Get output file extension.

        Args:
            options: Docling options

        Returns:
            File extension from options or default "md"
        """
        return options.get("write_extension", "md")


class TestEngine(TransformEngine):
    """Test engine that copies content."""

    def transform(self, input_path: Path, output_path: Path, options: dict[str, Any]) -> None:
        """Copy input to output."""
        content = input_path.read_text()
        output_path.write_text(f"Transformed: {content}")

    def get_extension(self, options: dict[str, Any]) -> str:
        """Get extension."""
        return "md"


# Registry of available engines
ENGINES: dict[str, TransformEngine] = {
    "docling": DoclingEngine(),
    "test": TestEngine(),
}


def get_engine(name: str) -> TransformEngine | None:
    """Get transform engine by name.

    Args:
        name: Engine name (e.g., "docling")

    Returns:
        Engine instance or None if not found
    """
    return ENGINES.get(name)
