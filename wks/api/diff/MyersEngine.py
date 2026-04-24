import subprocess
from pathlib import Path

from .DiffEngine import DiffEngine


class MyersEngine(DiffEngine):
    def diff(self, file1: Path, file2: Path, options: dict) -> str:
        if not self._is_text_file(file1):
            raise ValueError(f"{file1} is not a text file or has unsupported encoding")
        if not self._is_text_file(file2):
            raise ValueError(f"{file2} is not a text file or has unsupported encoding")

        context_lines = 3
        if "context_lines" in options:
            context_lines = options["context_lines"]

        cmd = ["diff", f"-U{context_lines}", str(file1), str(file2)]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,  # diff returns 1 for differences, which is OK
            )

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
        try:
            with file_path.open("rb") as f:
                chunk = f.read(8192)

            if b"\x00" in chunk:
                return False

            try:
                chunk.decode("utf-8")
                return True
            except UnicodeDecodeError:
                try:
                    chunk.decode("ascii")
                    return True
                except UnicodeDecodeError:
                    return False
        except Exception:
            return False
