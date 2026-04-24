"""Docling transform engine."""

import hashlib
import re
import shutil
import subprocess
import tempfile
from collections.abc import Generator
from pathlib import Path
from typing import Any

from .._TransformEngine import _TransformEngine


class _DoclingEngine(_TransformEngine):
    """Docling transform engine for PDF, DOCX, PPTX."""

    _LOG_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2},\d{3}\s+-\s+\w+\s+-\s+")
    _WORD_RE = re.compile(r"[A-Za-z]{3,}")
    _IMAGE_REF_RE = re.compile(r"(!\[[^\]]*\]\()([^)]+)(\))")

    def transform(
        self, input_path: Path, output_path: Path, options: dict[str, Any]
    ) -> Generator[str, None, list[str]]:
        """Transform document using docling with PDF recovery fallbacks."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_output = Path(temp_dir)
            out_format = options["to"]

            try:
                expected_output, referenced_images = yield from self._run_docling(
                    input_path,
                    output_path,
                    temp_output,
                    options,
                )
            except RuntimeError as exc:
                if self._should_try_pdf_recovery(input_path, out_format):
                    yield f"{exc}. Trying PDF recovery..."
                    recovered = yield from self._recover_pdf_text(input_path, options)
                    if recovered is not None:
                        output_path.write_text(recovered, encoding="utf-8")
                        return []
                raise
            except Exception as exc:
                raise RuntimeError(f"Docling error: {exc}") from exc

            if self._should_try_pdf_recovery(input_path, out_format):
                content = expected_output.read_text(encoding="utf-8", errors="replace")
                if self._is_low_quality_pdf_text(content, options):
                    yield "Docling output quality is low; trying PDF recovery..."
                    recovered = yield from self._recover_pdf_text(input_path, options)
                    if recovered is not None:
                        output_path.write_text(recovered, encoding="utf-8")
                        return []
                    raise RuntimeError("Docling produced low-quality PDF text and no usable fallback was available")

            output_path.write_bytes(expected_output.read_bytes())
            return referenced_images

    def get_extension(self, options: dict[str, Any]) -> str:
        """Get output file extension."""
        return options["to"]

    def _run_docling(
        self,
        input_path: Path,
        output_path: Path,
        temp_output: Path,
        options: dict[str, Any],
    ) -> Generator[str, None, tuple[Path, list[str]]]:
        """Run docling and return the expected output path plus referenced URIs."""
        cmd = ["docling", str(input_path), "--to", options["to"], "--output", str(temp_output)]

        ocr = options["ocr"]
        if ocr == "none" or ocr is False:
            cmd.append("--no-ocr")
        elif ocr:
            cmd.extend(["--ocr", "--ocr-engine", str(ocr)])

        ocr_languages = options["ocr_languages"]
        if ocr_languages:
            if isinstance(ocr_languages, list):
                ocr_languages = ",".join(ocr_languages)
            cmd.extend(["--ocr-lang", str(ocr_languages)])

        image_export_mode = options["image_export_mode"]
        cmd.extend(["--image-export-mode", str(image_export_mode)])
        cmd.extend(["--pipeline", str(options["pipeline"])])

        for flag in ("formula", "code", "picture_classes", "picture_description", "chart_extraction"):
            key = f"enrich_{flag}"
            if options.get(key):
                cmd.append(f"--enrich-{flag.replace('_', '-')}")

        timeout = self._coerce_timeout_secs(options.get("timeout_secs"))
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except OSError as exc:
            raise RuntimeError(f"Failed to start docling: {exc}") from exc

        try:
            if process.stdout:
                for line in process.stdout:
                    line = line.strip()
                    if line:
                        yield self._LOG_PREFIX_RE.sub("", line)

            try:
                return_code = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired as exc:
                process.kill()
                raise RuntimeError(f"Docling timed out after {timeout}s") from exc
        finally:
            if process.stdout:
                process.stdout.close()

        if return_code != 0:
            raise RuntimeError(f"Docling failed with exit code {return_code}")

        expected_output = temp_output / f"{input_path.stem}.{options['to']}"
        if not expected_output.exists():
            raise RuntimeError(f"Docling did not create expected output: {expected_output}")

        referenced_images = self._rewrite_referenced_images(
            expected_output,
            output_path,
            temp_output,
            image_export_mode,
        )
        return expected_output, referenced_images

    def _rewrite_referenced_images(
        self,
        expected_output: Path,
        output_path: Path,
        temp_output: Path,
        image_export_mode: str,
    ) -> list[str]:
        """Move referenced images into cache and rewrite markdown links."""
        if image_export_mode != "referenced":
            return []

        content = expected_output.read_text(encoding="utf-8")
        artifacts_dir = output_path.parent / f"{output_path.stem}_artifacts"
        referenced_images: list[str] = []
        used_names: set[str] = set()

        for img_file in self._iter_referenced_images(temp_output, expected_output):
            relative_path = img_file.relative_to(temp_output)
            cache_image_path = self._cache_image_path(artifacts_dir, relative_path, used_names)
            cache_image_path.parent.mkdir(parents=True, exist_ok=True)
            if not cache_image_path.exists():
                shutil.copy2(img_file, cache_image_path)

            from wks.api.config.URI import URI

            referenced_images.append(str(URI.from_path(cache_image_path)))
            content = self._rewrite_image_destination(content, img_file, relative_path, cache_image_path)

        expected_output.write_text(content, encoding="utf-8")
        return referenced_images

    def _iter_referenced_images(self, temp_output: Path, expected_output: Path) -> list[Path]:
        """Return all extracted image artifacts except the primary markdown output."""
        return sorted(path for path in temp_output.rglob("*") if path.is_file() and path != expected_output)

    def _cache_image_path(self, artifacts_dir: Path, relative_path: Path, used_names: set[str]) -> Path:
        """Return a stable cache-owned path for one extracted image artifact."""
        candidate_name = relative_path.name
        if candidate_name in used_names:
            suffix = hashlib.sha256(relative_path.as_posix().encode()).hexdigest()[:12]
            candidate_name = f"{relative_path.stem}_{suffix}{relative_path.suffix}"
        used_names.add(candidate_name)
        return artifacts_dir / candidate_name

    def _rewrite_image_destination(
        self,
        content: str,
        img_file: Path,
        relative_path: Path,
        cache_image_path: Path,
    ) -> str:
        """Rewrite one markdown image destination to a stable cache path."""
        replacements = {
            str(img_file),
            img_file.as_uri(),
            relative_path.as_posix(),
            relative_path.name,
        }
        rewritten_path = str(cache_image_path)

        def replace(match: re.Match[str]) -> str:
            destination = match.group(2).strip()
            unwrapped = (
                destination[1:-1].strip() if destination.startswith("<") and destination.endswith(">") else destination
            )
            if unwrapped not in replacements:
                return match.group(0)
            return f"{match.group(1)}{rewritten_path}{match.group(3)}"

        return self._IMAGE_REF_RE.sub(replace, content)

    def _recover_pdf_text(
        self,
        input_path: Path,
        options: dict[str, Any],
    ) -> Generator[str, None, str | None]:
        """Try pdftext then OCR, returning the first usable fallback text."""
        if self._coerce_bool(options.get("fallback_pdftext"), True):
            try:
                pdftext = yield from self._run_pdftext_fallback(input_path, options)
            except RuntimeError as exc:
                yield f"pdftotext fallback failed: {exc}"
            else:
                if not self._is_low_quality_pdf_text(pdftext, options):
                    return pdftext
                yield "pdftotext output quality is low"

        if self._coerce_bool(options.get("fallback_ocr"), True):
            try:
                ocr_text = yield from self._run_ocr_fallback(input_path, options)
            except RuntimeError as exc:
                yield f"OCR fallback failed: {exc}"
            else:
                if not self._is_low_quality_pdf_text(ocr_text, options):
                    return ocr_text
                yield "OCR output quality is low"

        return None

    def _run_pdftext_fallback(
        self,
        input_path: Path,
        options: dict[str, Any],
    ) -> Generator[str, None, str]:
        """Run the built-in pdftotext engine and return extracted text."""
        from .._pdftext._PdfTextEngine import _PdfTextEngine

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_output = Path(temp_dir) / "fallback.txt"
            pdftext = _PdfTextEngine()
            for message in pdftext.transform(input_path, temp_output, {"timeout_secs": options.get("timeout_secs")}):
                yield f"pdftotext fallback: {message}"
            return temp_output.read_text(encoding="utf-8", errors="replace")

    def _run_ocr_fallback(
        self,
        input_path: Path,
        options: dict[str, Any],
    ) -> Generator[str, None, str]:
        """OCR-render a PDF with pdftoppm+tesseract and return UTF-8 text."""
        timeout = self._coerce_timeout_secs(options.get("timeout_secs"))
        dpi = self._coerce_positive_int(options.get("ocr_fallback_dpi"), 300, "ocr_fallback_dpi")
        psm = self._coerce_positive_int(options.get("ocr_fallback_psm"), 6, "ocr_fallback_psm")
        language = self._tesseract_language(options.get("ocr_languages"))

        with tempfile.TemporaryDirectory() as temp_dir:
            prefix = Path(temp_dir) / "page"
            render_cmd = ["pdftoppm", "-r", str(dpi), "-png", str(input_path), str(prefix)]
            yield "OCR fallback: rendering PDF pages..."
            self._run_command(render_cmd, timeout, "pdftoppm")

            images = sorted(Path(temp_dir).glob("page-*.png"))
            if not images:
                raise RuntimeError("pdftoppm produced no page images")

            text_parts: list[str] = []
            for index, image_path in enumerate(images, start=1):
                ocr_cmd = ["tesseract", str(image_path), "stdout", "--psm", str(psm)]
                if language:
                    ocr_cmd.extend(["-l", language])
                yield f"OCR fallback: page {index}/{len(images)}..."
                text = self._run_command(ocr_cmd, timeout, "tesseract", capture_stdout=True)
                text_parts.append(text)

            return "\n\n\f\n\n".join(part.strip() for part in text_parts if part.strip())

    def _is_low_quality_pdf_text(self, text: str, options: dict[str, Any]) -> bool:
        """Return True when extracted PDF text is clearly low-quality."""
        visible_chars = [char for char in text if not char.isspace()]
        visible_count = len(visible_chars)
        if visible_count == 0:
            return True

        word_count = len(self._WORD_RE.findall(text))
        alpha_count = sum(char.isalpha() for char in visible_chars)
        bad_count = sum(char in {"ÿ", "�"} or (ord(char) < 32 and char not in "\n\r\t\f") for char in text)
        image_refs = text.count("![Image]") + text.count("![](")

        min_visible_chars = self._coerce_positive_int(
            options.get("quality_min_visible_chars"),
            500,
            "quality_min_visible_chars",
        )
        min_word_count = self._coerce_positive_int(options.get("quality_min_word_count"), 40, "quality_min_word_count")
        min_alpha_ratio = self._coerce_ratio(options.get("quality_min_alpha_ratio"), 0.25, "quality_min_alpha_ratio")
        max_bad_ratio = self._coerce_ratio(
            options.get("quality_max_bad_char_ratio"),
            0.10,
            "quality_max_bad_char_ratio",
        )

        alpha_ratio = alpha_count / visible_count
        bad_ratio = bad_count / visible_count

        if word_count == 0:
            return True
        if image_refs > 0 and (visible_count < min_visible_chars or word_count < min_word_count):
            return True
        if visible_count >= min_visible_chars and word_count < min_word_count:
            return True
        if visible_count >= min_visible_chars and alpha_ratio < min_alpha_ratio:
            return True
        return bad_ratio > max_bad_ratio

    @staticmethod
    def _should_try_pdf_recovery(input_path: Path, out_format: str) -> bool:
        """Return True when PDF fallback logic is applicable."""
        return input_path.suffix.lower() == ".pdf" and out_format == "md"

    @staticmethod
    def _run_command(
        cmd: list[str],
        timeout_secs: int | None,
        command_name: str,
        *,
        capture_stdout: bool = False,
    ) -> str:
        """Run a subprocess command and optionally return stdout."""
        try:
            completed = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_secs,
                check=False,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(f"{command_name} executable not found") from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"{command_name} timed out after {timeout_secs}s") from exc
        except OSError as exc:
            raise RuntimeError(f"Failed to start {command_name}: {exc}") from exc

        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()
            if detail:
                raise RuntimeError(f"{command_name} failed: {detail}")
            raise RuntimeError(f"{command_name} failed with exit code {completed.returncode}")

        return completed.stdout if capture_stdout else ""

    @staticmethod
    def _coerce_timeout_secs(value: Any) -> int | None:
        """Return a positive timeout in seconds when configured."""
        if value is None:
            return None
        try:
            timeout_secs = int(value)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("docling option 'timeout_secs' must be an integer") from exc
        if timeout_secs <= 0:
            raise RuntimeError("docling option 'timeout_secs' must be positive")
        return timeout_secs

    @staticmethod
    def _coerce_positive_int(value: Any, default: int, option_name: str) -> int:
        """Return a positive integer option or the provided default."""
        if value is None:
            return default
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"docling option '{option_name}' must be an integer") from exc
        if parsed <= 0:
            raise RuntimeError(f"docling option '{option_name}' must be positive")
        return parsed

    @staticmethod
    def _coerce_ratio(value: Any, default: float, option_name: str) -> float:
        """Return a ratio in the inclusive range [0, 1]."""
        if value is None:
            return default
        try:
            parsed = float(value)
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"docling option '{option_name}' must be numeric") from exc
        if parsed < 0 or parsed > 1:
            raise RuntimeError(f"docling option '{option_name}' must be between 0 and 1")
        return parsed

    @staticmethod
    def _coerce_bool(value: Any, default: bool) -> bool:
        """Return a bool with a default when unset."""
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"1", "true", "yes", "on"}:
                return True
            if lowered in {"0", "false", "no", "off"}:
                return False
        raise RuntimeError("docling fallback options must be boolean")

    @staticmethod
    def _tesseract_language(value: Any) -> str | None:
        """Convert WKS OCR language config into a tesseract-compatible value."""
        if value is None or value == "":
            return None
        if isinstance(value, list):
            parts = [str(item).strip() for item in value if str(item).strip()]
            return "+".join(parts) or None
        return str(value).replace(",", "+").strip() or None
