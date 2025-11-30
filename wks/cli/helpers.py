"""Shared helper functions for CLI commands."""

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple



from ..utils import file_checksum as _file_checksum_util


def maybe_write_json(args: Any, payload: Dict[str, Any]) -> None:
    """Write JSON output if --json flag is set."""
    if getattr(args, "json", False):
        json.dump(payload, sys.stdout, indent=2)
        sys.stdout.write("\n")
        sys.exit(0)


def as_file_uri_local(path: Path) -> str:
    """Convert path to file:// URI."""
    try:
        return path.expanduser().resolve().as_uri()
    except ValueError:
        return "file://" + path.expanduser().resolve().as_posix()





def file_checksum(path: Path) -> str:
    """Calculate file checksum."""
    return _file_checksum_util(path)


def iter_files(paths: List[str], include_exts: Optional[List[str]], cfg: Dict[str, Any]) -> List[Path]:
    """Iterate over files matching criteria."""
    from ..monitor import MonitorController

    def _should_skip(p: Path) -> bool:
        """Check if path should be skipped based on monitor rules."""
        try:
            result = MonitorController.check_path(str(p), cfg)
            return result.tracked is False
        except Exception:
            # If check fails, don't skip
            return False

    out: List[Path] = []
    for p in paths:
        pp = Path(p).expanduser()
        if not pp.exists():
            continue
        if _should_skip(pp):
            continue
        if pp.is_file():
            if not include_exts or pp.suffix.lower() in include_exts:
                out.append(pp)
        else:
            for x in pp.rglob('*'):
                if not x.is_file():
                    continue
                if _should_skip(x):
                    continue
                if include_exts and x.suffix.lower() not in include_exts:
                    continue
                out.append(x)
    return out


def make_progress(total: int, display: str = "cli"):
    """Create progress bar context manager."""
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn

    if display == "cli":
        class ProgressDriver:
            def __init__(self, total_steps: int):
                self._progress = Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                    console=None,
                )
                self._task_id = None
                self._total = max(total_steps, 1)
                self._started = False
                self._completed = 0

            def __enter__(self):
                self._progress.__enter__()
                self._task_id = self._progress.add_task("", total=self._total)
                return self

            def __exit__(self, exc_type, exc, tb):
                if self._task_id is not None and self._started:
                    remaining = self._total - self._completed
                    if remaining > 0:
                        self._progress.update(self._task_id, advance=remaining)
                self._progress.__exit__(exc_type, exc, tb)

            def update(self, description: str):
                if self._task_id is None:
                    return
                if not self._started:
                    self._progress.update(self._task_id, description=description)
                    self._started = True
                    return
                self._completed = min(self._completed + 1, self._total)
                self._progress.update(self._task_id, advance=1, description=description)

        return ProgressDriver(total)

    # No-op progress for non-CLI modes
    class NoOpProgress:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def update(self, *args, **kwargs):
            pass

    return NoOpProgress()


def display_status_table(
    display: Any,
    status_rows: List[Tuple[str, str]],
    title: str = "Status",
    *,
    key_width: Optional[int] = None,
    value_width: Optional[int] = None,
) -> None:
    """Display a status table using reflowing two-column layout."""
    from rich.table import Table
    from rich.panel import Panel
    from rich.columns import Columns
    from ..constants import MAX_DISPLAY_WIDTH

    if key_width is None:
        key_width = max(16, min(30, MAX_DISPLAY_WIDTH // 5))
    if value_width is None:
        value_width = max(10, min(20, MAX_DISPLAY_WIDTH // 8))

    row_tables = []
    for key, value in status_rows:
        row_table = Table(show_header=False, box=None, padding=(0, 1))
        row_table.add_column("Key", justify="left", width=key_width, overflow="fold")
        row_table.add_column("Value", justify="right", width=value_width)
        row_table.add_row(key, value)
        row_tables.append(row_table)

    columns = Columns(row_tables, equal=True, column_first=True, expand=True)
    panel = Panel.fit(columns, title=title, border_style="cyan", width=MAX_DISPLAY_WIDTH)
    display.console.print(panel)
