"""Shared helper functions for CLI commands."""

import argparse
import contextlib
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from fnmatch import fnmatchcase

from ..constants import WKS_DOT_DIRS
from ..extractor import Extractor


# Path and file utilities
def is_path_within(child: Path, base: Path) -> bool:
    """Check if child path is within base path."""
    try:
        child.resolve().relative_to(base.resolve())
        return True
    except Exception:
        return False


def should_auto_skip_path(p: Path) -> bool:
    """Check if path should be auto-skipped (WKS dot dirs)."""
    return any(part in WKS_DOT_DIRS for part in p.parts)


def is_excluded_by_path(p: Path, exclude_paths: List[Path]) -> bool:
    """Check if path is excluded by explicit exclude paths."""
    for ex in exclude_paths:
        if is_path_within(p, ex):
            return True
    return False


def is_excluded_by_dirname(p: Path, ignore_dirnames: Set[str]) -> bool:
    """Check if path is excluded by directory name."""
    for part in p.resolve().parts:
        if part in ignore_dirnames:
            return True
    return False


def is_excluded_by_glob(p: Path, ignore_globs: List[str]) -> bool:
    """Check if path is excluded by glob patterns."""
    pstr = p.as_posix()
    base = p.name
    for g in ignore_globs:
        try:
            if fnmatchcase(pstr, g) or fnmatchcase(base, g):
                return True
        except Exception:
            continue
    return False


def should_skip_by_monitor_rules(
    p: Path,
    respect: bool,
    exclude_paths: List[Path],
    ignore_dirnames: Set[str],
    ignore_globs: List[str]
) -> bool:
    """Check if path should be skipped by monitor rules."""
    if should_auto_skip_path(p):
        return True
    if not respect:
        return False

    return (is_excluded_by_path(p, exclude_paths) or
            is_excluded_by_dirname(p, ignore_dirnames) or
            is_excluded_by_glob(p, ignore_globs))


def matches_extension(p: Path, include_exts: List[str]) -> bool:
    """Check if file matches extension filter."""
    if not include_exts:
        return True
    return p.suffix.lower() in include_exts


def should_include_file(
    p: Path,
    include_exts: List[str],
    respect: bool,
    exclude_paths: List[Path],
    ignore_dirnames: Set[str],
    ignore_globs: List[str]
) -> bool:
    """Check if file should be included."""
    if not matches_extension(p, include_exts):
        return False
    if should_skip_by_monitor_rules(p, respect, exclude_paths, ignore_dirnames, ignore_globs):
        return False
    return True


def collect_files_from_path(
    pp: Path,
    include_exts: List[str],
    respect: bool,
    exclude_paths: List[Path],
    ignore_dirnames: Set[str],
    ignore_globs: List[str]
) -> List[Path]:
    """Collect files from a single path (file or directory)."""
    out: List[Path] = []

    if pp.is_file():
        if should_include_file(pp, include_exts, respect, exclude_paths, ignore_dirnames, ignore_globs):
            out.append(pp)
    else:
        for x in pp.rglob('*'):
            if not x.is_file():
                continue
            if should_auto_skip_path(x):
                continue
            if should_include_file(x, include_exts, respect, exclude_paths, ignore_dirnames, ignore_globs):
                out.append(x)
    return out


def iter_files(paths: List[str], include_exts: List[str], cfg: Dict[str, Any]) -> List[Path]:
    """Yield files under paths; optionally respect monitor ignores.

    By default, only extension filtering is applied (no implicit directory skips).
    If similarity.respect_monitor_ignores is true, uses monitor.exclude_paths,
    monitor.ignore_dirnames, and monitor.ignore_globs from config.
    """
    sim = cfg.get('similarity', {})
    respect = bool(sim.get('respect_monitor_ignores', False))
    mon = cfg.get('monitor', {}) if respect else {}
    exclude_paths = [Path(p).expanduser().resolve() for p in (mon.get('exclude_paths') or [])]
    ignore_dirnames = set(mon.get('ignore_dirnames') or [])
    ignore_globs = list(mon.get('ignore_globs') or [])

    out: List[Path] = []
    for p in paths:
        pp = Path(p).expanduser()
        if not pp.exists():
            continue
        if should_auto_skip_path(pp):
            continue
        files = collect_files_from_path(pp, include_exts, respect, exclude_paths, ignore_dirnames, ignore_globs)
        out.extend(files)
    return out


def build_extractor(cfg: Dict[str, Any]) -> Extractor:
    """Build extractor from config."""
    ext = cfg.get("extract") or {}
    sim = cfg.get("similarity") or {}
    return Extractor(
        engine=ext.get("engine", "docling"),
        ocr=bool(ext.get("ocr", False)),
        timeout_secs=int(ext.get("timeout_secs", 30)),
        options=dict(ext.get("options") or {}),
        max_chars=int(sim.get("max_chars", 200000)),
        write_extension=ext.get("write_extension"),
    )


def file_checksum(path: Path) -> str:
    """Compute SHA256 checksum of file."""
    hasher = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def as_file_uri_local(path: Path) -> str:
    """Convert path to file:// URI."""
    try:
        return path.expanduser().resolve().as_uri()
    except ValueError:
        return "file://" + path.expanduser().resolve().as_posix()


# Formatting utilities
def format_duration(seconds: float) -> str:
    """Format duration in seconds as human-readable string."""
    if seconds >= 1:
        return f"{seconds:.2f}s"
    return f"{seconds * 1000:.1f}ms"


def json_dumps(payload: Any) -> str:
    """Serialize payload to JSON string."""
    return json.dumps(payload, indent=2, ensure_ascii=False, default=str)


def maybe_write_json(args: argparse.Namespace, payload: Any) -> None:
    """Write JSON output if json_path is set in args."""
    path = getattr(args, "json_path", None)
    if not path:
        return
    text = json_dumps(payload)
    if path == "-":
        sys.__stdout__.write(text + "\n")
        sys.__stdout__.flush()
        return
    dest = Path(path).expanduser()
    try:
        parent = dest.parent
        if not parent.exists():
            parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text + "\n", encoding="utf-8")
    except Exception as exc:
        sys.__stderr__.write(f"Failed to write JSON output to {dest}: {exc}\n")


# Progress display
def make_progress(total: int, display: str):
    """Create progress context manager for file operations."""
    def _clip(text: str, limit: int = 48) -> str:
        if len(text) <= limit:
            return text
        if limit <= 1:
            return text[:limit]
        return text[: limit - 1] + "…"

    def _hms(secs: float) -> str:
        secs = max(0, int(secs))
        h = secs // 3600
        m = (secs % 3600) // 60
        s = secs % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    if display == "none":
        @contextmanager
        def _noop():
            class _Progress:
                def update(self, label: str, advance: int = 1) -> None:
                    return None

                def close(self) -> None:
                    return None

            yield _Progress()

        return _noop()

    if display == "cli":
        from rich.console import Console
        from rich.progress import (
            Progress,
            SpinnerColumn,
            BarColumn,
            TextColumn,
            TimeRemainingColumn,
            TimeElapsedColumn,
        )
        console = Console(
            force_terminal=True,
            color_system="standard",
            markup=True,
            highlight=False,
            soft_wrap=False,
        )
        spinner_style = "cyan"
        bar_complete = "green"
        bar_finished = "green"
        bar_pulse = "white"
        label_template = "{task.fields[current]:<36}"
        counter_template = "{task.completed}/{task.total}" if total else "{task.completed}"

        @contextmanager
        def _rp():
            start = time.perf_counter()
            last = {"label": "Starting"}
            with Progress(
                SpinnerColumn(style=spinner_style),
                TextColumn(label_template, justify="left"),
                BarColumn(
                    bar_width=32,
                    complete_style=bar_complete,
                    finished_style=bar_finished,
                    pulse_style=bar_pulse,
                ),
                TextColumn(counter_template, justify="right"),
                TimeRemainingColumn(),
                TimeElapsedColumn(),
                transient=False,
                console=console,
                refresh_per_second=12,
            ) as progress:
                task = progress.add_task(
                    "wks0",
                    total=total if total else None,
                    current="Starting",
                )

                class _RichProgress:
                    def update(self, label: str, advance: int = 1) -> None:
                        clipped = _clip(label)
                        last["label"] = clipped
                        progress.update(task, advance=advance, current=clipped)

                    def close(self) -> None:
                        return None

                yield _RichProgress()
            elapsed = time.perf_counter() - start
            label = last.get("label") or "Completed"
            console.print(
                f"{label} finished in {format_duration(elapsed)}",
                style="dim",
            )

        return _rp()

    @contextmanager
    def _bp():
        start = time.time()
        done = {"n": 0, "label": "Starting"}

        class _BasicProgress:
            def update(self, label: str, advance: int = 1) -> None:
                done["label"] = label
                done["n"] += advance
                n = done["n"]
                pct = (n / total * 100.0) if total else 100.0
                elapsed = time.time() - start
                eta = _hms((elapsed / n) * (total - n)) if n > 0 and total > n else _hms(0)
                print(f"[{n}/{total}] {pct:5.1f}% ETA {eta}  {label}")

            def close(self) -> None:
                return None

        try:
            yield _BasicProgress()
        finally:
            elapsed = time.time() - start
            label = done.get("label") or "Completed"
            print(f"[done] {label} finished in {format_duration(elapsed)}")

    return _bp()


# Naming utilities (for future use)
_DATE_RE = re.compile(r"^\d{4}(?:_\d{2})?(?:_\d{2})?$")
_GOOD_NAME_RE = re.compile(r"^[A-Za-z0-9_]+$")
_FOLDER_RE = re.compile(r"^(\d{4}(?:_\d{2})?(?:_\d{2})?)-([A-Za-z0-9_]+)$")


def sanitize_name(name: str) -> str:
    """Sanitize a name for use in file paths."""
    s = name.strip()
    s = s.replace('-', '_')
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^A-Za-z0-9_]", "_", s)
    s = re.sub(r"_+", "_", s)
    return s.strip('_') or "Untitled"


def normalize_date(date_str: str) -> str:
    """Normalize date string to YYYY_MM_DD format."""
    s = date_str.strip()
    s = s.replace('-', '_')
    if not _DATE_RE.match(s):
        raise ValueError(f"Invalid DATE format: {date_str}")
    # Validate components
    parts = s.split('_')
    y = int(parts[0])
    if y < 1900 or y > 3000:
        raise ValueError("YEAR out of range")
    if len(parts) > 1:
        m = int(parts[1])
        if m < 1 or m > 12:
            raise ValueError("MONTH out of range")
    if len(parts) > 2:
        d = int(parts[2])
        if d < 1 or d > 31:
            raise ValueError("DAY out of range")
    return s


def date_for_scope(scope: str, path: Path) -> str:
    """Get date string for a scope based on file mtime."""
    ts = int(path.stat().st_mtime) if path.exists() else int(time.time())
    lt = time.localtime(ts)
    if scope == 'project':
        return f"{lt.tm_year:04d}"
    if scope == 'document':
        return f"{lt.tm_year:04d}_{lt.tm_mon:02d}"
    if scope == 'deadline':
        return f"{lt.tm_year:04d}_{lt.tm_mon:02d}_{lt.tm_mday:02d}"
    raise ValueError("scope must be one of: project|document|deadline")


def pascalize_token(tok: str) -> str:
    """Pascalize a single token."""
    if not tok:
        return tok
    if tok.isupper() and tok.isalpha():
        return tok
    if tok.isalpha() and len(tok) <= 4:
        return tok.upper()
    return tok[:1].upper() + tok[1:].lower()


def pascalize_name(raw: str) -> str:
    """Convert raw name to PascalCase."""
    # Replace spaces and illegal chars with underscores, then collapse
    s = re.sub(r"[^A-Za-z0-9_\-]+", "_", raw.strip())
    s = re.sub(r"_+", "_", s).strip("_")
    # Split on hyphens to remove them from namestring
    parts = s.split('-')
    out_parts = []
    for part in parts:
        if '_' in part:
            subs = part.split('_')
            out_parts.append('_'.join(pascalize_token(t) for t in subs if t))
        else:
            out_parts.append(pascalize_token(part))
    return ''.join(out_parts)

