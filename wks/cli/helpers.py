"""Shared helper functions for CLI commands."""

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..constants import WKS_EXTRACT_EXT
from ..extractor import Extractor
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


def build_extractor(cfg: Dict[str, Any]) -> Extractor:
    """Build extractor from config."""
    ext = cfg.get("extract") or {}
    sim = cfg.get("related", {}).get("engines", {}).get("embedding", {}) or cfg.get("similarity") or {}
    return Extractor(
        engine=ext.get("engine", "docling"),
        ocr=bool(ext.get("ocr", False)),
        timeout_secs=int(ext.get("timeout_secs", 30)),
        options=dict(ext.get("options") or {}),
        max_chars=int(sim.get("max_chars", 200000)),
        write_extension=ext.get("write_extension"),
    )


def file_checksum(path: Path) -> str:
    """Calculate file checksum."""
    return _file_checksum_util(path)


def iter_files(paths: List[str], include_exts: Optional[List[str]], cfg: Dict[str, Any]) -> List[Path]:
    """Iterate over files matching criteria."""
    from ..monitor_controller import MonitorController
    
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
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=None,  # Will use default console
        )
    else:
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
    title: str = "Status"
) -> None:
    """Display a status table using reflowing two-column layout.
    
    This unified function is used by both service status and monitor status
    to ensure consistent table formatting.
    
    Args:
        display: Display object for rendering
        status_rows: List of (key, value) tuples for status data
        title: Panel title (default: "Status")
    """
    from rich.table import Table
    from rich.panel import Panel
    from rich.columns import Columns
    from ..constants import MAX_DISPLAY_WIDTH

    key_width = 22  # ~22 chars for key
    value_width = 10  # ~10 chars for value

    # Create individual table rows that will reflow into columns
    row_tables = []
    for key, value in status_rows:
        row_table = Table(show_header=False, box=None, padding=(0, 1))
        row_table.add_column("Key", justify="left", width=key_width)
        row_table.add_column("Value", justify="right", width=value_width)
        row_table.add_row(key, value)
        row_tables.append(row_table)
    
    # Use Columns with column_first=True for reflow layout
    # This will fill the first column, then the second column
    columns = Columns(row_tables, equal=True, column_first=True)

    # Display status panel
    panel = Panel.fit(columns, title=title, border_style="cyan", width=MAX_DISPLAY_WIDTH)
    display.console.print(panel)
