"""Transform engines for converting binary to text."""

import hashlib
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Optional


class TransformEngine(ABC):
    """Base class for transform engines."""

    @abstractmethod
    def transform(self, input_path: Path, output_path: Path, options: Dict[str, Any]) -> None:
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
    def get_extension(self, options: Dict[str, Any]) -> str:
        """Get output file extension for this engine.

        Args:
            options: Engine-specific options

        Returns:
            File extension (e.g., "md", "txt")
        """
        pass

    def compute_options_hash(self, options: Dict[str, Any]) -> str:
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

    def transform(self, input_path: Path, output_path: Path, options: Dict[str, Any]) -> None:
        """Transform document using docling.

        Args:
            input_path: Source file path
            output_path: Destination file path
            options: Docling options (ocr, timeout_secs, max_chars, etc.)

        Raises:
            RuntimeError: If docling command fails
        """
        cmd = ["docling", str(input_path), "--to", "md"]

        # Add OCR flag if enabled
        if options.get("ocr", False):
            cmd.append("--ocr")

        # Set timeout
        timeout = options.get("timeout_secs", 30)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=True
            )

            # Write output to file
            output_path.write_text(result.stdout, encoding="utf-8")

        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"Docling timed out after {timeout}s") from exc
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(f"Docling failed: {exc.stderr}") from exc
        except Exception as exc:
            raise RuntimeError(f"Docling error: {exc}") from exc

    def get_extension(self, options: Dict[str, Any]) -> str:
        """Get output file extension.

        Args:
            options: Docling options

        Returns:
            File extension from options or default "md"
        """
        return options.get("write_extension", "md")


# Registry of available engines
ENGINES: Dict[str, TransformEngine] = {
    "docling": DoclingEngine(),
}


def get_engine(name: str) -> Optional[TransformEngine]:
    """Get transform engine by name.

    Args:
        name: Engine name (e.g., "docling")

    Returns:
        Engine instance or None if not found
    """
    return ENGINES.get(name)
