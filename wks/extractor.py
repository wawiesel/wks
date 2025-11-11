from __future__ import annotations

import hashlib
import io
import logging
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from contextlib import redirect_stdout, redirect_stderr
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from .constants import WKS_EXTRACT_EXT


@dataclass
class ExtractResult:
    text: str
    content_path: Optional[Path]
    content_checksum: Optional[str]
    content_bytes: Optional[int]
    engine: str


class Extractor:
    """Shared document extraction helper used by wkso CLI and SimilarityDB."""

    def __init__(
        self,
        engine: str = "docling",
        *,
        ocr: bool = False,
        timeout_secs: int = 30,
        options: Optional[Dict[str, Any]] = None,
        max_chars: int = 200000,
        write_extension: Optional[str] = None,
    ) -> None:
        self.engine = (engine or "docling").lower()
        self.ocr = bool(ocr)
        self.timeout_secs = int(timeout_secs)
        self.options = dict(options or {})
        self.max_chars = int(max_chars)
        self.write_extension = write_extension or "md"
        if self.engine == "docling":
            self._suppress_docling_noise()

    # --- public API ----------------------------------------------------- #
    def extract(
        self,
        source: Path,
        *,
        persist: bool = True,
        output_dir: Optional[Path] = None,
    ) -> ExtractResult:
        """Extract text from ``source`` and optionally persist to disk."""

        source = source.expanduser().resolve()
        text, ext_hint = self._read_file_text(source)
        if not text or not text.strip():
            raise RuntimeError(f"No extractable text produced for {source}")
        text = text[: self.max_chars]

        if not persist:
            return ExtractResult(
                text=text,
                content_path=None,
                content_checksum=None,
                content_bytes=None,
                engine=self.engine,
            )

        checksum = hashlib.sha256(text.encode("utf-8")).hexdigest()
        ext = (ext_hint or self.write_extension or source.suffix.lstrip(".") or "txt").lstrip(".")
        if output_dir is None:
            repo_root = self._find_repo_root(source)
            if repo_root is not None:
                output_dir = repo_root.parent / WKS_EXTRACT_EXT
            else:
                output_dir = source.parent / WKS_EXTRACT_EXT
        output_dir.mkdir(parents=True, exist_ok=True)
        content_path = output_dir / f"{checksum}.{ext}"
        try:
            with open(content_path, "w", encoding="utf-8") as fh:
                fh.write(text)
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(f"Failed writing extracted text for {source}: {exc}") from exc

        try:
            content_bytes = content_path.stat().st_size
        except Exception:
            content_bytes = len(text.encode("utf-8"))

        return ExtractResult(
            text=text,
            content_path=content_path,
            content_checksum=checksum,
            content_bytes=content_bytes,
            engine=self.engine,
        )

    def read_text(self, source: Path) -> str:
        """Return extracted text without persisting to disk."""
        return self.extract(source, persist=False).text

    # --- engine-specific helpers --------------------------------------- #
    def _docling_convert(self, source: Path) -> str:
        try:
            from docling.document_converter import DocumentConverter
        except Exception as exc:  # pragma: no cover - docling missing
            raise RuntimeError("Docling extractor requested but not installed") from exc

        kwargs = dict(self.options)
        if self.ocr:
            kwargs.setdefault("ocr", True)
        converter = DocumentConverter(**kwargs)
        buffer = io.StringIO()
        with redirect_stdout(buffer), redirect_stderr(buffer):
            result = converter.convert(str(source))
        text = getattr(result, "text", None)
        if not text:
            doc = getattr(result, "document", None)
            if doc and hasattr(doc, "export_to_markdown"):
                try:
                    text = doc.export_to_markdown()
                except Exception:
                    text = None
        if not text:
            text = str(result)
        return text

    def _read_file_text(self, source: Path) -> Tuple[Optional[str], Optional[str]]:
        eff_max = self.max_chars
        if self.engine == "docling":
            try:
                text = self._docling_convert(source)
            except Exception:
                text = None
            if text and text.strip():
                return text, (self.write_extension or "md")
            fallback = self._read_builtin_text(source, eff_max)
            if fallback and fallback.strip():
                ext = source.suffix.lstrip(".") or "txt"
                return fallback, ext
            return None, None

        if self.engine == "builtin":
            text = self._read_builtin_text(source, eff_max)
            return text, (source.suffix.lstrip(".") or "txt")

        raise RuntimeError(f"Unsupported extractor engine: {self.engine}")

    # --- private helpers --------------------------------------------------- #
    _docling_quiet_applied = False

    @classmethod
    def _suppress_docling_noise(cls) -> None:
        if cls._docling_quiet_applied:
            return
        cls._docling_quiet_applied = True
        # Reduce logging verbosity from docling and related libraries
        for name in [
            "docling",
            "docling.document_converter",
            "docling_core",
            "docling.pipeline",
            "docling.pipeline.simple_pipeline",
        ]:
            logging.getLogger(name).setLevel(logging.WARNING)
        # Disable tqdm progress bars emitted by docling pipelines
        os.environ.setdefault("TQDM_DISABLE", "1")
        os.environ.setdefault("DISABLE_TQDM", "1")
        os.environ.setdefault("DOC_PARSER_DISABLE_TQDM", "1")
        os.environ.setdefault("DOC_PARSER_DISABLE_PROGRESS", "1")

    # --- builtin fallback ------------------------------------------------ #
    def _read_builtin_text(self, source: Path, max_chars: int) -> Optional[str]:
        suffix = source.suffix.lower()
        # simple text formats
        if suffix in {".txt", ".md", ".py", ".json", ".yaml", ".yml", ".toml", ".tex", ".rst"}:
            try:
                with open(source, "r", encoding="utf-8", errors="ignore") as fh:
                    return fh.read(max_chars)
            except Exception:
                return None

        if suffix == ".docx":
            return self._extract_docx_text(source, max_chars)
        if suffix == ".pptx":
            return self._extract_pptx_text(source, max_chars)
        if suffix == ".pdf":
            return self._extract_pdf_text(source, max_chars)

        try:
            with open(source, "r", encoding="utf-8", errors="ignore") as fh:
                return fh.read(max_chars)
        except Exception:
            return None

    @staticmethod
    def _find_repo_root(path: Path) -> Optional[Path]:
        try:
            for parent in [path.parent] + list(path.parents):
                git_dir = parent / ".git"
                if git_dir.exists():
                    return parent
        except Exception:
            return None
        return None

    def _extract_docx_text(self, path: Path, max_chars: int) -> Optional[str]:
        try:
            with zipfile.ZipFile(path) as zf:
                with zf.open("word/document.xml") as fh:
                    xml_bytes = fh.read()
            import xml.etree.ElementTree as ET

            root = ET.fromstring(xml_bytes)
            ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
            texts = [node.text for node in root.findall(".//w:t", ns) if node.text]
            return "\n".join(texts)[:max_chars]
        except Exception:
            return None

    def _extract_pptx_text(self, path: Path, max_chars: int) -> Optional[str]:
        try:
            with zipfile.ZipFile(path) as zf:
                slide_names = [n for n in zf.namelist() if n.startswith("ppt/slides/slide") and n.endswith(".xml")]
                texts = []
                import xml.etree.ElementTree as ET

                ns = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
                for name in sorted(slide_names):
                    try:
                        with zf.open(name) as fh:
                            xml_bytes = fh.read()
                        root = ET.fromstring(xml_bytes)
                        for node in root.findall(".//a:t", ns):
                            if node.text:
                                texts.append(node.text)
                    except Exception:
                        continue
            return "\n".join(texts)[:max_chars]
        except Exception:
            return None

    def _extract_pdf_text(self, path: Path, max_chars: int) -> Optional[str]:
        try:
            if shutil.which("pdftotext"):
                with tempfile.NamedTemporaryFile(suffix=".txt", delete=True) as tmp:
                    subprocess.run(
                        ["pdftotext", "-layout", str(path), tmp.name],
                        check=False,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=self.timeout_secs,
                    )
                    try:
                        txt = Path(tmp.name).read_text(encoding="utf-8", errors="ignore")
                        if txt and txt.strip():
                            return txt[:max_chars]
                    except Exception:
                        pass
        except Exception:
            pass

        try:
            if shutil.which("strings"):
                out = subprocess.check_output(
                    ["strings", "-n", "4", str(path)],
                    stderr=subprocess.DEVNULL,
                    timeout=self.timeout_secs,
                )
                txt = out.decode("utf-8", errors="ignore")
                txt = re.sub(r"\s+", " ", txt)
                return txt[:max_chars]
        except Exception:
            pass
        return None
