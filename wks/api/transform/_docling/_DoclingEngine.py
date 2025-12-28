"""Docling transform engine."""

import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .._TransformEngine import _TransformEngine


class _DoclingEngine(_TransformEngine):
    """Docling transform engine for PDF, DOCX, PPTX."""

    def transform(self, input_path: Path, output_path: Path, options: dict[str, Any]) -> None:
        """Transform document using docling.

        Args:
            input_path: Source file path
            output_path: Destination file path
            options: Docling options:
                - ocr: "none" to disable, or engine name like "tesseract", "easyocr"
                - ocr_languages: Comma-separated languages like "eng,deu"
                - image_export_mode: "placeholder", "embedded", "referenced"
                - pipeline: "standard" or "vlm"
                - timeout_secs: Timeout in seconds (default 30)

        Raises:
            RuntimeError: If docling command fails
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_output = Path(temp_dir)

            cmd = ["docling", str(input_path), "--to", "md", "--output", str(temp_output)]

            # OCR handling: "none" disables, any other value is engine name
            ocr = options.get("ocr")
            if ocr == "none" or ocr is False:
                cmd.append("--no-ocr")
            elif ocr:
                cmd.extend(["--ocr", "--ocr-engine", str(ocr)])

            # OCR languages
            ocr_languages = options.get("ocr_languages")
            if ocr_languages:
                cmd.extend(["--ocr-languages", str(ocr_languages)])

            # Image export mode
            image_export_mode = options.get("image_export_mode")
            if image_export_mode:
                cmd.extend(["--image-export-mode", str(image_export_mode)])

            # Pipeline
            pipeline = options.get("pipeline")
            if pipeline:
                cmd.extend(["--pipeline", str(pipeline)])

            # Timeout
            timeout = options.get("timeout_secs", 30)

            try:
                subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=True)

                # Docling writes <input_stem>.md to output directory
                expected_output = temp_output / f"{input_path.stem}.md"

                if not expected_output.exists():
                    raise RuntimeError(f"Docling did not create expected output: {expected_output}")

                output_path.write_bytes(expected_output.read_bytes())

            except subprocess.TimeoutExpired as exc:
                raise RuntimeError(f"Docling timed out after {timeout}s") from exc
            except subprocess.CalledProcessError as exc:
                raise RuntimeError(f"Docling failed: {exc.stderr}") from exc
            except Exception as exc:
                raise RuntimeError(f"Docling error: {exc}") from exc

    def get_extension(self, options: dict[str, Any]) -> str:
        """Get output file extension."""
        return options.get("write_extension", "md")
