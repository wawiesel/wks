from pathlib import Path


def select_auto_diff_engine(file1: Path, file2: Path) -> str:
    if file1.suffix == ".sexp" and file2.suffix == ".sexp":
        return "sexp"

    def is_text_file(file_path: Path) -> bool:
        try:
            with file_path.open("rb") as f:
                chunk = f.read(8192)
                if b"\x00" in chunk:
                    return False
                try:
                    chunk.decode("utf-8")
                    return True
                except UnicodeDecodeError:
                    return False
        except Exception:
            return False

    if is_text_file(file1) and is_text_file(file2):
        return "myers"

    return "bsdiff3"


__all__ = ["select_auto_diff_engine"]
