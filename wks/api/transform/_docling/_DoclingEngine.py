"""Docling transform engine."""

import re
import subprocess
import tempfile
from collections.abc import Generator
from pathlib import Path
from typing import Any

from .._TransformEngine import _TransformEngine


class _DoclingEngine(_TransformEngine):
    """Docling transform engine for PDF, DOCX, PPTX."""

    def transform(
        self, input_path: Path, output_path: Path, options: dict[str, Any]
    ) -> Generator[str, None, list[str]]:
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

            # Use 'to' to set output format
            out_format = options["to"]
            cmd = ["docling", str(input_path), "--to", out_format, "--output", str(temp_output)]

            # OCR handling: "none" disables, any other value is engine name
            ocr = options["ocr"]
            if ocr == "none" or ocr is False:
                cmd.append("--no-ocr")
            elif ocr:
                cmd.extend(["--ocr", "--ocr-engine", str(ocr)])

            # OCR languages (required)
            ocr_languages = options["ocr_languages"]
            if ocr_languages:
                if isinstance(ocr_languages, list):
                    ocr_languages = ",".join(ocr_languages)
                cmd.extend(["--ocr-languages", str(ocr_languages)])

            # Image export mode (required)
            image_export_mode = options["image_export_mode"]
            cmd.extend(["--image-export-mode", str(image_export_mode)])

            # Pipeline (required)
            pipeline = options["pipeline"]
            cmd.extend(["--pipeline", str(pipeline)])

            # Timeout (required)
            timeout = options["timeout_secs"]

            # Start process
            try:
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,  # Line buffered
                )

                # Stream output
                # Regex to strip standard logging prefix: "YYYY-MM-DD HH:MM:SS,mmm - LEVEL - "
                log_prefix_re = re.compile(r"^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2},\d{3}\s+-\s+\w+\s+-\s+")

                if process.stdout:
                    for line in process.stdout:
                        line = line.strip()
                        if line:
                            # Strip prefix if present
                            clean_line = log_prefix_re.sub("", line)
                            yield clean_line

                # Wait for completion
                try:
                    return_code = process.wait(timeout=timeout)
                except subprocess.TimeoutExpired as exc:
                    process.kill()
                    raise RuntimeError(f"Docling timed out after {timeout}s") from exc

                if return_code != 0:
                    raise RuntimeError(f"Docling failed with exit code {return_code}")

                # Docling writes <input_stem>.<ext> to output directory
                # Note: docling might normalize extension (e.g. json -> json)
                expected_output = temp_output / f"{input_path.stem}.{out_format}"

                if not expected_output.exists():
                    raise RuntimeError(f"Docling did not create expected output: {expected_output}")

                referenced_images = []

                # Handle referenced images
                if image_export_mode == "referenced":
                    # Images are expected in the temp output directory
                    # We need to:
                    # 1. Find them
                    # 2. Checksum them
                    # 3. Move them to cache
                    # 4. Update the markdown to point to them

                    content = expected_output.read_text(encoding="utf-8")

                    # Docling names images like <stem>_page_1_figure_1.png
                    # We iterate all potential image files in the temp dir
                    for img_file in temp_output.glob("*"):
                        if img_file.name == expected_output.name:
                            continue

                        # Start calculating checksum
                        yield f"Processing image {img_file.name}..."

                        # Compute checksum
                        import hashlib

                        sha256 = hashlib.sha256()
                        sha256.update(img_file.read_bytes())
                        checksum = sha256.hexdigest()

                        # Target path in cache
                        # Preserve extension
                        ext = img_file.suffix.lstrip(".")
                        cache_image_path = output_path.parent / f"{checksum}.{ext}"

                        # Move to cache (or copy if using temp)
                        if not cache_image_path.exists():
                            # Atomic move might produce cross-device link error if temp is on different volume
                            # Copy is safer
                            import shutil

                            shutil.copy2(img_file, cache_image_path)

                        # Record for return value
                        from ...utils.path_to_uri import path_to_uri

                        referenced_images.append(path_to_uri(cache_image_path))

                        # Rewrite content: replace relative path with absolute cache URI
                        # Docling likely uses relative path in markdown: ![](stem_page_1.png)
                        # We replace `img_file.name` with `cache_image_path` absolute path?
                        # Or file URI? The spec says "absolute file URI".
                        # Markdown standard image link: ![alt](path)
                        # We need to be careful not to replace partial matches.

                        # Simple replacement of filename
                        # This assumes docling uses just the filename in the link, which is standard for same-dir output
                        content = content.replace(img_file.name, path_to_uri(cache_image_path))

                    # Write updated content back to expected_output so it gets copied to output_path next
                    expected_output.write_text(content, encoding="utf-8")

                output_path.write_bytes(expected_output.read_bytes())

                return referenced_images

            except Exception as exc:
                if isinstance(exc, RuntimeError):
                    raise
                raise RuntimeError(f"Docling error: {exc}") from exc

    def get_extension(self, options: dict[str, Any]) -> str:
        """Get output file extension."""
        return options["to"]
