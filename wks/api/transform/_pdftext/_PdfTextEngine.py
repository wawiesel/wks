import subprocess
from collections.abc import Generator
from pathlib import Path
from typing import Any

from .._TransformEngine import _TransformEngine


class _PdfTextEngine(_TransformEngine):
    def transform(
        self,
        input_path: Path,
        output_path: Path,
        options: dict[str, Any],
    ) -> Generator[str, None, list[str]]:
        timeout_secs = self._coerce_timeout_secs(options.get("timeout_secs"))
        cmd = ["pdftotext", "-enc", "UTF-8", str(input_path), "-"]

        yield "Running pdftotext..."
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
            raise RuntimeError("pdftotext executable not found") from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"pdftotext timed out after {timeout_secs}s") from exc
        except OSError as exc:
            raise RuntimeError(f"Failed to start pdftotext: {exc}") from exc

        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()
            if detail:
                raise RuntimeError(f"pdftotext failed: {detail}")
            raise RuntimeError(f"pdftotext failed with exit code {completed.returncode}")

        yield "Writing extracted text..."
        try:
            output_path.write_text(completed.stdout, encoding="utf-8")
        except OSError as exc:
            raise RuntimeError(f"Failed to write extracted text: {exc}") from exc

        yield "PDF text extraction complete"
        return []

    def get_extension(self, options: dict[str, Any]) -> str:  # noqa: ARG002
        return "txt"

    @staticmethod
    def _coerce_timeout_secs(value: Any) -> int | None:
        if value is None:
            return None
        try:
            timeout_secs = int(value)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("pdftext option 'timeout_secs' must be an integer") from exc

        if timeout_secs <= 0:
            raise RuntimeError("pdftext option 'timeout_secs' must be positive")
        return timeout_secs
