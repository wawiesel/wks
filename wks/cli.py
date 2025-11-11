"""
WKS command-line interface.

Provides simple commands for managing the daemon, config, and local MongoDB.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import math
import os
import platform
import re
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
import json
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import unquote, urlparse

import fnmatch
import pymongo
import shutil

from .config import (
    apply_similarity_mongo_defaults,
    mongo_settings,
    DEFAULT_TIMESTAMP_FORMAT,
    timestamp_format,
    load_user_config,
)
from .constants import WKS_HOME_EXT, WKS_EXTRACT_EXT, WKS_DOT_DIRS, WKS_HOME_DISPLAY
from .display.context import get_display, add_display_argument
from .extractor import Extractor
from .status import record_db_activity, load_db_activity_summary, load_db_activity_history
from .dbmeta import (
    IncompatibleDatabase,
    ensure_db_compat,
    resolve_db_compatibility,
)
from .utils import get_package_version
from . import mongoctl
from .templating import render_template


LOCK_FILE = Path.home() / WKS_HOME_EXT / "daemon.lock"

DEFAULT_MONITOR_INCLUDE_PATHS = ["~"]
DEFAULT_MONITOR_EXCLUDE_PATHS = ["~/Library", "~/obsidian", f"{WKS_HOME_DISPLAY}"]
DEFAULT_MONITOR_IGNORE_DIRS = [".git", "_build", WKS_HOME_EXT, WKS_EXTRACT_EXT]
DEFAULT_MONITOR_IGNORE_GLOBS = ["*.tmp", "*~", "._*"]

DEFAULT_OBSIDIAN_CONFIG = {
    "base_dir": "WKS",
    "log_max_entries": 500,
    "active_files_max_rows": 50,
    "source_max_chars": 40,
    "destination_max_chars": 40,
    "docs_keep": 99,
}

DEFAULT_SIMILARITY_EXTS = [
    ".md",
    ".txt",
    ".py",
    ".ipynb",
    ".tex",
    ".docx",
    ".pptx",
    ".pdf",
    ".html",
    ".csv",
    ".xlsx",
]

# Legacy display modes (mapped to cli/mcp internally)
DISPLAY_CHOICES_LEGACY = ["auto", "rich", "plain", "markdown", "json", "none"]
# New display modes
DISPLAY_CHOICES = ["cli", "mcp"]

STATUS_MARKDOWN_TEMPLATE = """| Key | Value |
| --- | --- |
{% for key, value in rows %}
| {{ key }} | {{ value | replace('|', '\\|') | replace('\n', '<br>') }} |
{% endfor %}
""".strip()

DB_QUERY_MARKDOWN_TEMPLATE = """### {{ scope|capitalize }} query — {{ collection }}
{% if rows %}
| # | Document |
| --- | --- |
{% for row in rows %}
| {{ loop.index }} | {{ row | replace('|', '\\|') }} |
{% endfor %}
{% else %}
_No documents found._
{% endif %}
""".strip()


# _package_version moved to utils.get_package_version


def _human_bytes(value: Optional[int]) -> str:
    if value is None:
        return "-"
    try:
        val = float(value)
    except Exception:
        return "-"
    units = ["B", "kB", "MB", "GB", "TB"]
    idx = 0
    while val >= 1024.0 and idx < len(units) - 1:
        val /= 1024.0
        idx += 1
    return f"{val:7.2f} {units[idx]:>2}"


def _fmt_bool(value: Optional[bool]) -> str:
    if value is None:
        return "-"
    return "true" if value else "false"


def _format_timestamp_value(value: Optional[Any], fmt: str) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    try:
        s = text
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        s = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
    except Exception:
        try:
            fallback = text.replace("T", " ").replace("Z", "")
            dt = datetime.fromisoformat(fallback)
        except Exception:
            return text
    try:
        return dt.strftime(fmt)
    except Exception:
        return text


def _doc_path_to_local(doc: Dict[str, Any]) -> Optional[Path]:
    local = doc.get("path_local")
    if isinstance(local, str) and local:
        try:
            return Path(local).expanduser()
        except Exception:
            pass
    uri = doc.get("path")
    if isinstance(uri, str) and uri:
        if uri.startswith("file://"):
            try:
                parsed = urlparse(uri)
                return Path(unquote(parsed.path or "")).expanduser()
            except Exception:
                return None
        try:
            return Path(uri).expanduser()
        except Exception:
            return None
    return None


@dataclass
class ServiceStatusLaunch:
    state: Optional[str] = None
    active_count: Optional[str] = None
    pid: Optional[str] = None
    program: Optional[str] = None
    arguments: Optional[str] = None
    working_dir: Optional[str] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    runs: Optional[str] = None
    last_exit: Optional[str] = None
    path: Optional[str] = None
    type: Optional[str] = None

    def present(self) -> bool:
        return any(
            [
                self.state,
                self.pid,
                self.program,
                self.arguments,
                self.working_dir,
                self.stdout,
                self.stderr,
                self.path,
            ]
        )

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ServiceStatusDB:
    tracked_files: Optional[int] = None
    last_updated: Optional[str] = None
    total_size_bytes: Optional[int] = None
    latest_files: List[Dict[str, str]] = field(default_factory=list)

    def present(self) -> bool:
        return any(
            [
                self.tracked_files is not None,
                self.last_updated,
                self.total_size_bytes is not None,
                self.latest_files,
            ]
        )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "tracked_files": self.tracked_files,
            "last_updated": self.last_updated,
            "total_size_bytes": self.total_size_bytes,
            "latest_files": list(self.latest_files),
        }


@dataclass
class ServiceStatusData:
    running: Optional[bool] = None
    heartbeat: Optional[str] = None
    uptime: Optional[str] = None
    pid: Optional[int] = None
    beats_per_min: Optional[float] = None
    pending_deletes: Optional[int] = None
    pending_mods: Optional[int] = None
    ok: Optional[bool] = None
    lock: Optional[bool] = None
    last_error: Optional[str] = None
    db_last_operation: Optional[str] = None
    db_last_operation_detail: Optional[str] = None
    db_last_operation_iso: Optional[str] = None
    db_ops_last_minute: Optional[int] = None
    fs_rate_short: Optional[float] = None
    fs_rate_long: Optional[float] = None
    fs_rate_weighted: Optional[float] = None
    launch: ServiceStatusLaunch = field(default_factory=ServiceStatusLaunch)
    db: ServiceStatusDB = field(default_factory=ServiceStatusDB)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "service": {
                "running": self.running,
                "heartbeat": self.heartbeat,
                "uptime": self.uptime,
                "pid": self.pid,
                "beats_per_min": self.beats_per_min,
                "pending_deletes": self.pending_deletes,
                "pending_mods": self.pending_mods,
                "ok": self.ok,
                "lock": self.lock,
                "last_error": self.last_error,
                "db_last_operation": self.db_last_operation,
                "db_last_operation_detail": self.db_last_operation_detail,
                "db_last_operation_iso": self.db_last_operation_iso,
                "db_ops_last_minute": self.db_ops_last_minute,
                "fs_rate_short": self.fs_rate_short,
                "fs_rate_long": self.fs_rate_long,
                "fs_rate_weighted": self.fs_rate_weighted,
            },
            "launch_agent": self.launch.as_dict(),
            "space_db": self.db.as_dict(),
            "notes": list(self.notes),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    def to_rows(self) -> List[Tuple[str, str]]:
        rows: List[Tuple[str, str]] = []
        rows.append(("Running", _fmt_bool(self.running)))
        rows.append(("Heartbeat", self.heartbeat or "-"))
        rows.append(("Uptime", self.uptime or "-"))
        rows.append(("PID", str(self.pid) if self.pid is not None else "-"))
        rows.append(
            ("DB ops/min", f"{self.beats_per_min:.2f}" if isinstance(self.beats_per_min, (int, float)) else "-")
        )
        rows.append(
            ("Pending deletes", str(self.pending_deletes) if self.pending_deletes is not None else "-")
        )
        rows.append(("Pending mods", str(self.pending_mods) if self.pending_mods is not None else "-"))
        rows.append(("OK", _fmt_bool(self.ok)))
        rows.append(("Lock", _fmt_bool(self.lock)))
        if self.last_error:
            rows.append(("Last error", self.last_error))
        if self.db_last_operation or self.db_last_operation_iso:
            desc = self.db_last_operation or "-"
            if self.db_last_operation_detail:
                desc = f"{desc} ({self.db_last_operation_detail})"
            if self.db_last_operation_iso:
                desc = f"{desc} @ {self.db_last_operation_iso}"
            rows.append(("Last operation", desc))
        if self.db_ops_last_minute is not None:
            rows.append(("DB ops (last min)", str(self.db_ops_last_minute)))
        if self.fs_rate_short is not None:
            rows.append(("FS ops/sec (10s)", f"{self.fs_rate_short:.2f}"))
        if self.fs_rate_long is not None:
            rows.append(("FS ops/sec (10m)", f"{self.fs_rate_long:.2f}"))
        if self.fs_rate_weighted is not None:
            rows.append(("FS ops/sec (weighted)", f"{self.fs_rate_weighted:.2f}"))
        if self.launch.present():
            rows.append(("Launch state", self.launch.state or "-"))
            rows.append(("Launch PID", self.launch.pid or "-"))
            program_desc = self.launch.arguments or self.launch.program or "-"
            rows.append(("Launch program", program_desc))
            rows.append(("Launch stdout", self.launch.stdout or "-"))
            rows.append(("Launch stderr", self.launch.stderr or "-"))
            rows.append(("Launch runs", self.launch.runs or "-"))
            rows.append(("Launch last exit", self.launch.last_exit or "-"))
            rows.append(("Launch path", self.launch.path or "-"))
            rows.append(("Launch type", self.launch.type or "-"))
        if self.db.present():
            rows.append(
                (
                    "DB tracked files",
                    str(self.db.tracked_files) if self.db.tracked_files is not None else "-",
                )
            )
            rows.append(("DB last updated", self.db.last_updated or "-"))
            rows.append(
                (
                    "DB total size",
                    _human_bytes(self.db.total_size_bytes),
                )
            )
        if self.notes:
            rows.append(("Notes", "; ".join(self.notes)))
        return rows

    def to_markdown(self) -> str:
        rows = self.to_rows()
        lines = ["| Key | Value |", "| --- | --- |"]
        for key, value in rows:
            val = value if value else "-"
            val = val.replace("|", "\\|").replace("\n", "<br>")
            lines.append(f"| {key} | {val} |")
        return "\n".join(lines)

def load_config() -> Dict[str, Any]:
    return load_user_config()


def _merge_defaults(defaults: List[str], user: Optional[List[str]]) -> List[str]:
    merged: List[str] = []
    for item in defaults:
        if item not in merged:
            merged.append(item)
    for item in user or []:
        if item not in merged:
            merged.append(item)
    return merged


def print_config(args: argparse.Namespace) -> None:
    cfg = load_config()
    mongo_cfg = mongo_settings(cfg)
    space_tag, time_tag = resolve_db_compatibility(cfg)
    mongo_out = dict(mongo_cfg)
    mongo_out["compatibility"] = {
        "space": space_tag,
        "time": time_tag,
    }

    obs_raw = cfg.get("obsidian") or {}
    obsidian = {
        "base_dir": obs_raw.get("base_dir", DEFAULT_OBSIDIAN_CONFIG["base_dir"]),
        "log_max_entries": int(obs_raw.get("log_max_entries", DEFAULT_OBSIDIAN_CONFIG["log_max_entries"])),
        "active_files_max_rows": int(obs_raw.get("active_files_max_rows", DEFAULT_OBSIDIAN_CONFIG["active_files_max_rows"])),
        "source_max_chars": int(obs_raw.get("source_max_chars", DEFAULT_OBSIDIAN_CONFIG["source_max_chars"])),
        "destination_max_chars": int(obs_raw.get("destination_max_chars", DEFAULT_OBSIDIAN_CONFIG["destination_max_chars"])),
        "docs_keep": int(obs_raw.get("docs_keep", DEFAULT_OBSIDIAN_CONFIG["docs_keep"])),
    }

    mon_raw = cfg.get("monitor") or {}
    monitor = {
        "include_paths": _merge_defaults(DEFAULT_MONITOR_INCLUDE_PATHS, mon_raw.get("include_paths")),
        "exclude_paths": _merge_defaults(DEFAULT_MONITOR_EXCLUDE_PATHS, mon_raw.get("exclude_paths")),
        "ignore_dirnames": _merge_defaults(DEFAULT_MONITOR_IGNORE_DIRS, mon_raw.get("ignore_dirnames")),
        "ignore_globs": _merge_defaults(DEFAULT_MONITOR_IGNORE_GLOBS, mon_raw.get("ignore_globs")),
        "state_file": mon_raw.get("state_file", f"{WKS_HOME_DISPLAY}/monitor_state.json"),
    }

    activity_raw = cfg.get("activity") or {}
    activity = {
        "state_file": activity_raw.get("state_file", f"{WKS_HOME_DISPLAY}/activity_state.json"),
    }

    display_cfg = cfg.get("display") or {}
    display = {
        "timestamp_format": display_cfg.get("timestamp_format", timestamp_format(cfg) or DEFAULT_TIMESTAMP_FORMAT),
    }

    ext_raw = cfg.get("extract") or {}
    extract = {
        "engine": ext_raw.get("engine", "docling"),
        "ocr": bool(ext_raw.get("ocr", False)),
        "timeout_secs": int(ext_raw.get("timeout_secs", 30)),
        "options": dict(ext_raw.get("options") or {}),
    }

    sim_raw = cfg.get("similarity") or {}
    include_exts = sim_raw.get("include_extensions")
    if not include_exts:
        include_exts = DEFAULT_SIMILARITY_EXTS
    similarity = {
        "enabled": bool(sim_raw.get("enabled", True)),
        "model": sim_raw.get("model", "all-MiniLM-L6-v2"),
        "include_extensions": [ext.lower() for ext in include_exts],
        "min_chars": int(sim_raw.get("min_chars", 10)),
        "max_chars": int(sim_raw.get("max_chars", 200000)),
        "chunk_chars": int(sim_raw.get("chunk_chars", 1500)),
        "chunk_overlap": int(sim_raw.get("chunk_overlap", 200)),
        "offline": bool(sim_raw.get("offline", True)),
        "respect_monitor_ignores": bool(sim_raw.get("respect_monitor_ignores", False)),
    }

    metrics_raw = cfg.get("metrics") or {}
    metrics = {
        "fs_rate_short_window_secs": int(metrics_raw.get("fs_rate_short_window_secs", 10)),
        "fs_rate_long_window_secs": int(metrics_raw.get("fs_rate_long_window_secs", 600)),
        "fs_rate_short_weight": float(metrics_raw.get("fs_rate_short_weight", 0.8)),
        "fs_rate_long_weight": float(metrics_raw.get("fs_rate_long_weight", 0.2)),
    }

    payload = {
        "vault_path": cfg.get("vault_path", "~/obsidian"),
        "obsidian": obsidian,
        "monitor": monitor,
        "activity": activity,
        "display": display,
        "mongo": mongo_out,
        "extract": extract,
        "similarity": similarity,
        "metrics": metrics,
    }

    _maybe_write_json(args, payload)
    if not _display_enabled(args.display):
        return
    if args.display == "rich":
        try:
            from rich.console import Console
            from rich.syntax import Syntax

            Console().print(Syntax(_json_dumps(payload), "json", word_wrap=False, indent_guides=True))
            return
        except Exception:
            pass
    print(_json_dumps(payload))


def _pid_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def _stop_managed_mongo() -> None:
    mongoctl.stop_managed_mongo()


def _agent_label() -> str:
    # Unique launchd label bound to the new CLI name
    return "com.wieselquist.wkso"


def _agent_plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{_agent_label()}.plist"


def _is_macos() -> bool:
    return platform.system() == "Darwin"


def _launchctl(*args: str) -> int:
    try:
        # Suppress noisy stderr/stdout from launchctl; we use return codes
        return subprocess.call(["launchctl", *args], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        return 2


def _agent_installed() -> bool:
    return _agent_plist_path().exists()


def _daemon_start_launchd():
    uid = os.getuid()
    pl = str(_agent_plist_path())
    # Prefer kickstart for already-bootstrapped agents
    rc = _launchctl("kickstart", "-k", f"gui/{uid}/{_agent_label()}")
    if rc == 0:
        return
    # If kickstart failed, try bootstrapping fresh
    _launchctl("bootout", f"gui/{uid}", pl)
    _launchctl("bootstrap", f"gui/{uid}", pl)
    _launchctl("enable", f"gui/{uid}/{_agent_label()}")
    _launchctl("kickstart", "-k", f"gui/{uid}/{_agent_label()}")


def _daemon_stop_launchd():
    uid = os.getuid()
    _launchctl("bootout", f"gui/{uid}", str(_agent_plist_path()))


def _daemon_status_launchd() -> int:
    uid = os.getuid()
    try:
        return subprocess.call(["launchctl", "print", f"gui/{uid}/{_agent_label()}"])
    except Exception:
        return 3


def daemon_status(args: argparse.Namespace) -> int:
    status = ServiceStatusData()

    try:
        mongoctl.ensure_mongo_running(_default_mongo_uri(), record_start=False)
    except Exception:
        pass

    @dataclass
    class LaunchAgentStatusInternal:
        state: str = ""
        active_count: str = ""
        path: str = ""
        type: str = ""
        program: str = ""
        arguments: str = ""
        working_dir: str = ""
        stdout: str = ""
        stderr: str = ""
        runs: str = ""
        pid: str = ""
        last_exit: str = ""

    launch_info: Optional[LaunchAgentStatusInternal] = None
    if _is_macos() and _agent_installed():
        try:
            uid = os.getuid()
            out = subprocess.check_output(
                ["launchctl", "print", f"gui/{uid}/{_agent_label()}"],
                stderr=subprocess.STDOUT,
            )
            launch_text = out.decode("utf-8", errors="ignore")
            import re as _re

            def _find(pattern: str, default: str = "") -> str:
                match = _re.search(pattern, launch_text)
                return match.group(1).strip() if match else default

            launch_info = LaunchAgentStatusInternal(
                active_count=_find(r"active count =\s*(\d+)"),
                path=_find(r"\n\s*path =\s*(.*)"),
                type=_find(r"\n\s*type =\s*(.*)"),
                state=_find(r"\n\s*state =\s*(.*)"),
                program=_find(r"\n\s*program =\s*(.*)"),
                working_dir=_find(r"\n\s*working directory =\s*(.*)"),
                stdout=_find(r"\n\s*stdout path =\s*(.*)"),
                stderr=_find(r"\n\s*stderr path =\s*(.*)"),
                runs=_find(r"\n\s*runs =\s*(\d+)"),
                pid=_find(r"\n\s*pid =\s*(\d+)"),
                last_exit=_find(r"\n\s*last exit code =\s*(\d+)"),
            )
            try:
                args_block = _re.search(r"arguments = \{([^}]*)\}", launch_text, _re.DOTALL)
                if args_block:
                    lines = [ln.strip() for ln in args_block.group(1).splitlines() if ln.strip()]
                    if launch_info:
                        launch_info.arguments = " ".join(lines)
            except Exception:
                pass
        except Exception:
            status.notes.append("Launch agent status unavailable")

    if launch_info:
        status.launch = ServiceStatusLaunch(
            state=launch_info.state or None,
            active_count=launch_info.active_count or None,
            pid=launch_info.pid or None,
            program=launch_info.program or None,
            arguments=launch_info.arguments or None,
            working_dir=launch_info.working_dir or None,
            stdout=launch_info.stdout or None,
            stderr=launch_info.stderr or None,
            runs=launch_info.runs or None,
            last_exit=launch_info.last_exit or None,
            path=launch_info.path or None,
            type=launch_info.type or None,
        )

    health_path = Path.home() / WKS_HOME_EXT / "health.json"
    health: Dict[str, Any] = {}
    try:
        if health_path.exists():
            health = json.load(open(health_path, "r"))
    except Exception:
        status.notes.append("Failed to read health metrics")
        health = {}

    if health:
        status.running = bool(health.get("lock_present"))
        status.heartbeat = str(health.get("heartbeat_iso") or "")
        status.uptime = str(health.get("uptime_hms") or "")
        try:
            status.pid = int(health.get("pid"))
        except Exception:
            status.pid = None
        try:
            bpm = health.get("avg_beats_per_min")
            status.beats_per_min = float(bpm) if bpm is not None else None
        except Exception:
            status.beats_per_min = None
        status.pending_deletes = health.get("pending_deletes")
        status.pending_mods = health.get("pending_mods")
        status.ok = False if health.get("last_error") else True
        status.lock = bool(health.get("lock_present"))
        if health.get("last_error"):
            status.last_error = str(health.get("last_error"))
        if health.get("db_last_operation"):
            status.db_last_operation = health.get("db_last_operation")
        if health.get("db_last_operation_detail"):
            status.db_last_operation_detail = health.get("db_last_operation_detail")
        if health.get("db_last_operation_iso"):
            status.db_last_operation_iso = health.get("db_last_operation_iso")
        if health.get("db_ops_last_minute") is not None:
            try:
                status.db_ops_last_minute = int(health.get("db_ops_last_minute"))
            except Exception:
                status.db_ops_last_minute = None
        for attr, key in [
            ("fs_rate_short", "fs_rate_short"),
            ("fs_rate_long", "fs_rate_long"),
            ("fs_rate_weighted", "fs_rate_weighted"),
        ]:
            try:
                val = health.get(key)
                setattr(status, attr, float(val) if val is not None else None)
            except Exception:
                setattr(status, attr, None)
    else:
        lock_exists = LOCK_FILE.exists()
        status.lock = lock_exists
        if lock_exists:
            try:
                pid = int(LOCK_FILE.read_text().strip().splitlines()[0])
                status.pid = pid
                status.running = _pid_running(pid)
            except Exception:
                status.notes.append("Lock present but PID unavailable")
                status.running = None
        else:
            status.running = False
        if not status.notes and not lock_exists:
            status.notes.append("WKS daemon: not running")

    summary = load_db_activity_summary()
    if summary:
        if not status.db_last_operation:
            status.db_last_operation = summary.get("operation") or None
        if not status.db_last_operation_detail:
            status.db_last_operation_detail = summary.get("detail") or None
        if not status.db_last_operation_iso:
            status.db_last_operation_iso = summary.get("timestamp_iso") or None
        if not status.heartbeat:
            status.heartbeat = summary.get("timestamp_iso") or status.heartbeat

    recent = load_db_activity_history(60)
    if status.db_ops_last_minute is None:
        status.db_ops_last_minute = len(recent)
    if status.beats_per_min is None and recent:
        status.beats_per_min = float(len(recent))
    if status.beats_per_min is None:
        status.beats_per_min = float(status.db_ops_last_minute or 0)

    try:
        cfg = load_config()
        ts_format = timestamp_format(cfg)
        mongo_cfg = mongo_settings(cfg)
        space_tag, _ = resolve_db_compatibility(cfg)
        client = pymongo.MongoClient(
            mongo_cfg["uri"],
            serverSelectionTimeoutMS=300,
            connectTimeoutMS=300,
        )
        client.admin.command("ping")
        try:
            ensure_db_compat(
                client,
                mongo_cfg["space_database"],
                "space",
                space_tag,
                product_version=get_package_version(),
            )
        except IncompatibleDatabase as exc:
            status.notes.append(str(exc))
            try:
                client.close()
            except Exception:
                pass
            coll = None
        else:
            coll = client[mongo_cfg["space_database"]][mongo_cfg["space_collection"]]
        if coll is not None:
            status.db.tracked_files = coll.count_documents({})
            last_doc = coll.find({}, {"timestamp": 1}).sort("timestamp", -1).limit(1)
            for doc in last_doc:
                formatted = _format_timestamp_value(doc.get("timestamp"), ts_format)
                status.db.last_updated = formatted or str(doc.get("timestamp", ""))

            total_size: Optional[int] = None
            try:
                agg = coll.aggregate(
                    [{"$group": {"_id": None, "total": {"$sum": {"$cond": [{"$gt": ["$bytes", 0]}, "$bytes", 0]}}}}]
                )
                agg_doc = next(agg, None)
                if agg_doc and agg_doc.get("total") is not None:
                    total_candidate = agg_doc.get("total")
                    if isinstance(total_candidate, (int, float)):
                        total_size = int(total_candidate)
            except Exception:
                total_size = None

            if total_size in (None, 0):
                try:
                    approx_total = 0
                    found_any = False
                    missing_metadata = False
                    for doc in coll.find({}, {"path": 1, "path_local": 1, "bytes": 1}).limit(1000):
                        found_any = True
                        bval = doc.get("bytes")
                        if isinstance(bval, (int, float)) and bval > 0:
                            approx_total += int(bval)
                            continue
                        missing_metadata = True
                        local_path = _doc_path_to_local(doc)
                        if local_path and local_path.exists():
                            try:
                                approx_total += local_path.stat().st_size
                            except Exception:
                                pass
                    if found_any and approx_total > 0:
                        total_size = approx_total
                    elif not missing_metadata and total_size is None:
                        total_size = approx_total
                except Exception:
                    pass

            if isinstance(total_size, (int, float)) and total_size >= 0:
                status.db.total_size_bytes = int(total_size)
            else:
                status.db.total_size_bytes = None
            latest = coll.find({}, {"path": 1, "timestamp": 1}).sort("timestamp", -1).limit(5)
            records = []
            for doc in latest:
                ts_value = _format_timestamp_value(doc.get("timestamp"), ts_format)
                if not ts_value:
                    ts_value = str(doc.get("timestamp", ""))
                records.append({"timestamp": ts_value, "path": str(doc.get("path", ""))})
            status.db.latest_files = records
            try:
                client.close()
            except Exception:
                pass
    except SystemExit:
        raise
    except Exception as exc:
        status.notes.append(f"Space DB stats unavailable: {exc}")

    payload = status.to_dict()
    _maybe_write_json(args, payload)

    display_mode = args.display
    if display_mode == "none":
        return 0
    if display_mode == "json":
        print(_json_dumps(payload))
        return 0
    if display_mode == "markdown":
        print(render_template(STATUS_MARKDOWN_TEMPLATE, {"rows": status.to_rows()}))
        return 0

    use_rich = False
    plain_mode = False
    if display_mode == "rich":
        use_rich = True
    elif display_mode == "plain":
        use_rich = True
        plain_mode = True
    elif display_mode == "auto":
        try:
            use_rich = sys.stdout.isatty()
        except Exception:
            use_rich = False

    if use_rich:
        try:
            from rich import box
            from rich.console import Console
            from rich.table import Table
        except Exception:
            use_rich = False

    if use_rich:
        colorful = (display_mode in {"rich", "auto"}) and not plain_mode
        console = Console(
            force_terminal=True,
            color_system=None if colorful else "standard",
            markup=colorful,
            highlight=False,
            soft_wrap=False,
        )
        table = Table(
            title="WKS Service Status",
            header_style="bold" if colorful else "",
            box=box.SQUARE if colorful else box.SIMPLE,
            expand=False,
            pad_edge=False,
        )
        table.add_column("Key", style="cyan" if colorful else "", overflow="fold")
        table.add_column("Value", style="white" if colorful else "", overflow="fold")
        for key, value in status.to_rows():
            table.add_row(key, value)
        console.print(table)
        return 0

    print(_json_dumps(payload))
    return 0


def _read_health_snapshot() -> Dict[str, Any]:
    health_path = Path.home() / WKS_HOME_EXT / "health.json"
    if not health_path.exists():
        return {}
    try:
        with open(health_path, "r") as fh:
            return json.load(fh)
    except Exception:
        return {}


def _wait_for_health_update(previous_heartbeat: Optional[str], timeout: float = 5.0) -> None:
    health_path = Path.home() / WKS_HOME_EXT / "health.json"
    if timeout <= 0:
        return
    deadline = time.time() + timeout
    while time.time() < deadline:
        if health_path.exists():
            try:
                with open(health_path, "r") as fh:
                    data = json.load(fh)
                hb = data.get("heartbeat_iso") or str(data.get("heartbeat"))
                if hb and hb != previous_heartbeat:
                    return
            except Exception:
                pass
        time.sleep(0.25)


def daemon_start(_: argparse.Namespace):
    mongoctl.ensure_mongo_running(_default_mongo_uri(), record_start=True)
    if _is_macos() and _agent_installed():
        _daemon_start_launchd()
        return
    # Start as background process: python -m wks.daemon
    env = os.environ.copy()
    python = sys.executable
    log_dir = Path.home() / WKS_HOME_EXT
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "daemon.log"
    # Prefer running against the local source tree when available
    try:
        proj_root = Path(__file__).resolve().parents[1]
        env["PYTHONPATH"] = f"{proj_root}:{env.get('PYTHONPATH','')}"
        workdir = str(proj_root)
    except Exception:
        workdir = None
    with open(log_file, "ab", buffering=0) as lf:
        # Detach: create a new session
        kwargs = {
            "stdout": lf,
            "stderr": lf,
            "stdin": subprocess.DEVNULL,
            "start_new_session": True,
            "env": env,
            **({"cwd": workdir} if workdir else {}),
        }
        try:
            p = subprocess.Popen([python, "-m", "wks.daemon"], **kwargs)
        except Exception as e:
            print(f"Failed to start daemon: {e}")
            sys.exit(1)
    print(f"WKS daemon started (PID {p.pid}). Log: {log_file}")


def _daemon_stop_core(stop_mongo: bool = True) -> None:
    if _is_macos() and _agent_installed():
        _daemon_stop_launchd()
        if stop_mongo:
            _stop_managed_mongo()
        return
    if not LOCK_FILE.exists():
        print("WKS daemon is not running")
        if stop_mongo:
            _stop_managed_mongo()
        return
    try:
        pid_line = LOCK_FILE.read_text().strip().splitlines()[0]
        pid = int(pid_line)
    except Exception:
        print("Could not read PID from lock; try killing manually")
        return
    try:
        os.kill(pid, signal.SIGTERM)
        print(f"Sent SIGTERM to PID {pid}")
    except Exception as e:
        print(f"Failed to send SIGTERM to PID {pid}: {e}")
    finally:
        if stop_mongo:
            _stop_managed_mongo()


def daemon_stop(_: argparse.Namespace):
    _daemon_stop_core(stop_mongo=True)


def daemon_restart(args: argparse.Namespace):
    previous_health = _read_health_snapshot()
    previous_heartbeat = previous_health.get("heartbeat_iso") or previous_health.get("heartbeat")

    # macOS launchd-managed restart
    if _is_macos() and _agent_installed():
        try:
            mongoctl.ensure_mongo_running(_default_mongo_uri(), record_start=True)
        except Exception:
            pass
        try:
            _daemon_stop_launchd()
        except Exception:
            pass
        time.sleep(0.5)
        _daemon_start_launchd()
        _wait_for_health_update(previous_heartbeat, timeout=5.0)
        return

    # Fallback: stop/start without touching databases
    try:
        _daemon_stop_core(stop_mongo=False)
    except Exception:
        pass
    time.sleep(0.5)
    try:
        mongoctl.ensure_mongo_running(_default_mongo_uri(), record_start=True)
    except Exception:
        pass
    daemon_start(args)
    _wait_for_health_update(previous_heartbeat, timeout=5.0)




# ----------------------------- Similarity CLI ------------------------------ #
def _build_similarity_from_config(require_enabled: bool = True):
    try:
        from .similarity import build_similarity_from_config  # type: ignore
    except ImportError as e:
        error_msg = str(e).lower()
        if "sentence" in error_msg or "transformers" in error_msg:
            from .error_messages import missing_dependency_error
            missing_dependency_error("sentence-transformers", e)
        elif "docling" in error_msg:
            from .error_messages import missing_dependency_error
            missing_dependency_error("docling", e)
        else:
            print(f"\nSimilarity features not available: {e}")
            print("Install with: pip install -e '.[all]'\n")
            if require_enabled:
                raise SystemExit(2)
        return None, None
    except Exception as e:
        print(f"Similarity not available: {e}")
        if require_enabled:
            raise SystemExit(2)
        return None, None
    cfg = load_config()
    space_tag, _ = resolve_db_compatibility(cfg)
    pkg_version = get_package_version()
    try:
        db, sim_cfg = build_similarity_from_config(
            cfg,
            require_enabled=require_enabled,
            compatibility_tag=space_tag,
            product_version=pkg_version,
        )
        return db, sim_cfg
    except IncompatibleDatabase as exc:
        print(exc)
        if require_enabled:
            raise SystemExit(2)
        return None, None
    except Exception as e:
        mongo_uri = mongo_settings(cfg)["uri"]
        if mongo_uri.startswith("mongodb://localhost:27027") and shutil.which("mongod"):
            dbroot = Path.home() / WKS_HOME_EXT / "mongodb"
            dbpath = dbroot / "db"
            logfile = dbroot / "mongod.log"
            dbpath.mkdir(parents=True, exist_ok=True)
            try:
                subprocess.check_call([
                    "mongod", "--dbpath", str(dbpath), "--logpath", str(logfile),
                    "--fork", "--bind_ip", "127.0.0.1", "--port", "27027"
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                db, sim_cfg = build_similarity_from_config(
                    cfg,
                    require_enabled=require_enabled,
                    compatibility_tag=space_tag,
                    product_version=pkg_version,
                )
                return db, sim_cfg
            except IncompatibleDatabase as exc2:
                print(exc2)
                if require_enabled:
                    raise SystemExit(2)
                return None, None
            except Exception as e2:
                print(f"Failed to auto-start local mongod: {e2}")
                if require_enabled:
                    raise SystemExit(2)
                return None, None
        print(f"Failed to initialize similarity DB: {e}")
        if require_enabled:
            raise SystemExit(2)
        return None, None


def _load_similarity_db() -> Any:
    db, _ = _build_similarity_from_config(require_enabled=False)
    return db


def _iter_files(paths: List[str], include_exts: List[str], cfg: Dict[str, Any]) -> List[Path]:
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

    def _is_within(child: Path, base: Path) -> bool:
        try:
            child.resolve().relative_to(base.resolve())
            return True
        except Exception:
            return False

    def _auto_skip(p: Path) -> bool:
        parts = p.parts
        return any(part in WKS_DOT_DIRS for part in parts)

    def _skip(p: Path) -> bool:
        if _auto_skip(p):
            return True
        if not respect:
            return False
        # Exclude explicit paths
        for ex in exclude_paths:
            if _is_within(p, ex):
                return True
        # Ignore if any directory segment is in ignore_dirnames
        for part in p.resolve().parts:
            if part in ignore_dirnames:
                return True
        # Glob-based ignores
        pstr = p.as_posix()
        base = p.name
        from fnmatch import fnmatchcase as _fn
        for g in ignore_globs:
            try:
                if _fn(pstr, g) or _fn(base, g):
                    return True
            except Exception:
                continue
        return False

    out: List[Path] = []
    for p in paths:
        pp = Path(p).expanduser()
        if not pp.exists():
            continue
        if _auto_skip(pp):
            continue
        if pp.is_file():
            if (not include_exts or pp.suffix.lower() in include_exts) and not _skip(pp):
                out.append(pp)
        else:
            for x in pp.rglob('*'):
                if not x.is_file():
                    continue
                if _auto_skip(x):
                    continue
                if include_exts and x.suffix.lower() not in include_exts:
                    continue
                if _skip(x):
                    continue
                out.append(x)
    return out


def _build_extractor(cfg: Dict[str, Any]) -> Extractor:
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


def _file_checksum(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def _as_file_uri_local(path: Path) -> str:
    try:
        return path.expanduser().resolve().as_uri()
    except ValueError:
        return "file://" + path.expanduser().resolve().as_posix()


def _format_duration(seconds: float) -> str:
    if seconds >= 1:
        return f"{seconds:.2f}s"
    return f"{seconds * 1000:.1f}ms"


def _resolve_display_mode(args: argparse.Namespace, default: str = "rich") -> str:
    mode = getattr(args, "display", None) or default
    if mode not in DISPLAY_CHOICES:
        return default
    return mode


def _display_enabled(mode: str) -> bool:
    return mode != "none"


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False, default=str)


def _maybe_write_json(args: argparse.Namespace, payload: Any) -> None:
    path = getattr(args, "json_path", None)
    if not path:
        return
    text = _json_dumps(payload)
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


def _make_progress(total: int, display: str):
    from contextlib import contextmanager
    import time

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

    use_rich = display in {"rich", "plain"}
    if use_rich:
        try:
            from rich.console import Console
            from rich.progress import (
                Progress,
                SpinnerColumn,
                BarColumn,
                TextColumn,
                TimeRemainingColumn,
                TimeElapsedColumn,
            )
        except Exception:
            use_rich = False

    if use_rich:
        console = Console(
            force_terminal=True,
            color_system=None if display == "rich" else "standard",
            markup=(display == "rich"),
            highlight=False,
            soft_wrap=False,
        )
        spinner_style = "cyan" if display == "rich" else ""
        bar_complete = "green" if display == "rich" else "white"
        bar_finished = "green" if display == "rich" else "white"
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
                    "wkso",
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
                f"{label} finished in {_format_duration(elapsed)}",
                style="dim" if display == "rich" else "",
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
            print(f"[done] {label} finished in {_format_duration(elapsed)}")

    return _bp()


# ----------------------------- LLM helpers --------------------------------- # (removed)

# ----------------------------- Naming utilities ---------------------------- #
_DATE_RE = re.compile(r"^\d{4}(?:_\d{2})?(?:_\d{2})?$")
_GOOD_NAME_RE = re.compile(r"^[A-Za-z0-9_]+$")
_FOLDER_RE = re.compile(r"^(\d{4}(?:_\d{2})?(?:_\d{2})?)-([A-Za-z0-9_]+)$")


def _sanitize_name(name: str) -> str:
    s = name.strip()
    s = s.replace('-', '_')
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^A-Za-z0-9_]", "_", s)
    s = re.sub(r"_+", "_", s)
    return s.strip('_') or "Untitled"


def _normalize_date(date_str: str) -> str:
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


def _date_for_scope(scope: str, path: Path) -> str:
    ts = int(path.stat().st_mtime) if path.exists() else int(time.time())
    lt = time.localtime(ts)
    if scope == 'project':
        return f"{lt.tm_year:04d}"
    if scope == 'document':
        return f"{lt.tm_year:04d}_{lt.tm_mon:02d}"
    if scope == 'deadline':
        return f"{lt.tm_year:04d}_{lt.tm_mon:02d}_{lt.tm_mday:02d}"
    raise ValueError("scope must be one of: project|document|deadline")


# names_route_cmd removed


def names_check_cmd(args: argparse.Namespace) -> int:
    # Removed: analyze helpers are not part of the minimal CLI
    print("names check is not available in this build")
    return 2


def _pascalize_token(tok: str) -> str:
    if not tok:
        return tok
    if tok.isupper() and tok.isalpha():
        return tok
    if tok.isalpha() and len(tok) <= 4:
        return tok.upper()
    return tok[:1].upper() + tok[1:].lower()


def _pascalize_name(raw: str) -> str:
    # Replace spaces and illegal chars with underscores, then collapse
    s = re.sub(r"[^A-Za-z0-9_\-]+", "_", raw.strip())
    s = re.sub(r"_+", "_", s).strip("_")
    # Split on hyphens to remove them from namestring
    parts = s.split('-')
    out_parts = []
    for part in parts:
        if '_' in part:
            subs = part.split('_')
            out_parts.append('_'.join(_pascalize_token(t) for t in subs if t))
        else:
            out_parts.append(_pascalize_token(part))
    return ''.join(out_parts)


# names fix features removed


def _load_similarity_required() -> Tuple[Any, Dict[str, Any]]:
    db, sim_cfg = _build_similarity_from_config(require_enabled=True)
    if db is None or sim_cfg is None:
        raise SystemExit(2)
    return db, sim_cfg


# migration removed


def _mongo_client_params(
    server_timeout: int = 500,
    connect_timeout: int = 500,
    cfg: Optional[Dict[str, Any]] = None,
    *,
    ensure_running: bool = True,
) -> Tuple[pymongo.MongoClient, Dict[str, str]]:
    """Return (client, normalized mongo settings)."""
    if cfg is None:
        cfg = load_config()
    mongo_cfg = mongo_settings(cfg)
    client = mongoctl.create_client(
        mongo_cfg['uri'],
        server_timeout=server_timeout,
        connect_timeout=connect_timeout,
        ensure_running=ensure_running,
    )
    return client, mongo_cfg


def _default_mongo_uri() -> str:
    return mongo_settings(load_config())['uri']


def _is_within(path: Path, base: Path) -> bool:
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except Exception:
        return False


def _should_skip_dir(dirpath: Path, ignore_dirnames: List[str]) -> bool:
    parts = dirpath.parts
    for part in parts:
        if part in ignore_dirnames:
            return True
        if part in WKS_DOT_DIRS:
            return True
        if part.startswith('.'):
            return True
    return False


def _should_skip_file(path: Path, ignore_patterns: List[str], ignore_globs: List[str]) -> bool:
    # Dotfiles (including .wks/.wkso artefact directories)
    if path.name.startswith('.') or any(part in WKS_DOT_DIRS for part in path.parts):
        return True
    # Pattern tokens match any segment exactly
    for tok in ignore_patterns:
        if tok in path.parts:
            return True
    # Glob matches against full path and basename
    pstr = path.as_posix()
    for g in ignore_globs:
        if fnmatch.fnmatchcase(pstr, g) or fnmatch.fnmatchcase(path.name, g):
            return True
    return False


"""Backfill removed for simplicity."""


# ----------------------------- Obsidian helpers ---------------------------- #
def _load_vault() -> Any:
    from .obsidian import ObsidianVault  # lazy import
    cfg = load_config()
    vault_path = cfg.get('vault_path')
    if not vault_path:
        print(f"Fatal: 'vault_path' is required in {WKS_HOME_DISPLAY}/config.json")
        raise SystemExit(2)
    obs = cfg.get('obsidian', {})
    base_dir = obs.get('base_dir')
    if not base_dir:
        print(f"Fatal: 'obsidian.base_dir' is required in {WKS_HOME_DISPLAY}/config.json (e.g., 'WKS')")
        raise SystemExit(2)
    # Require explicit logging caps/widths
    for k in ["log_max_entries", "active_files_max_rows", "source_max_chars", "destination_max_chars"]:
        if k not in obs:
            print(f"Fatal: missing required config key: obsidian.{k}")
            raise SystemExit(2)
    vault = ObsidianVault(
        Path(vault_path).expanduser(),
        base_dir=base_dir,
        log_max_entries=int(obs["log_max_entries"]),
        active_files_max_rows=int(obs["active_files_max_rows"]),
        source_max_chars=int(obs["source_max_chars"]),
        destination_max_chars=int(obs["destination_max_chars"]),
    )
    return vault


"""Unnecessary helpers removed for simplicity (obs connect, debug match, init logs, etc.)."""


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="wkso", description="WKS management CLI")
    sub = parser.add_subparsers(dest="cmd")
    # Global display mode
    pkg_version = get_package_version()
    git_sha = ""
    try:
        repo_root = Path(__file__).resolve().parents[1]
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            cwd=str(repo_root),
        )
        git_sha = out.decode("utf-8", errors="ignore").strip()
    except Exception:
        git_sha = ""
    version_str = f"wkso {pkg_version}"
    if git_sha:
        version_str = f"{version_str} ({git_sha})"
    parser.add_argument(
        "--version",
        action="version",
        version=version_str,
        help="Show CLI version and exit",
    )
    # Add --display argument (cli or mcp, auto-detected)
    add_display_argument(parser)
    parser.add_argument(
        "--json",
        dest="json_path",
        help="Optional path to write structured JSON output; use '-' for stdout.",
    )

    # Lightweight progress helpers
    cfg = sub.add_parser("config", help="Config commands")
    cfg_sub = cfg.add_subparsers(dest="cfg_cmd")
    cfg_print = cfg_sub.add_parser("print", help="Print effective config")
    cfg_print.set_defaults(func=print_config)

    # Service management (macOS launchd)

    

    # Optional install/uninstall on macOS (hide behind help)
    def _launchctl_quiet(*args: str) -> int:
        try:
            return subprocess.call(["launchctl", *args], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            print("launchctl not found; macOS only")
            return 2

    def _plist_path() -> Path:
        return Path.home()/"Library"/"LaunchAgents"/"com.wieselquist.wkso.plist"

    def daemon_install(args: argparse.Namespace):
        if platform.system() != "Darwin":
            print("install is macOS-only (launchd)")
            return
        pl = _plist_path()
        pl.parent.mkdir(parents=True, exist_ok=True)
        log_dir = Path.home()/WKS_HOME_EXT
        log_dir.mkdir(exist_ok=True)
        # Use the current interpreter (works for system Python, venv, and pipx)
        python = sys.executable
        proj_root = Path(__file__).resolve().parents[1]
        xml = f"""
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.wieselquist.wkso</string>
  <key>LimitLoadToSessionType</key>
  <string>Aqua</string>
  <key>ProgramArguments</key>
  <array>
    <string>{python}</string>
    <string>-m</string>
    <string>wks.daemon</string>
  </array>
  <key>WorkingDirectory</key>
  <string>{proj_root}</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PYTHONPATH</key>
    <string>{proj_root}</string>
    <key>TOKENIZERS_PARALLELISM</key>
    <string>false</string>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>{log_dir}/daemon.log</string>
  <key>StandardErrorPath</key>
  <string>{log_dir}/daemon.error.log</string>
 </dict>
</plist>
""".strip()
        pl.write_text(xml)
        uid = os.getuid()
        with _make_progress(total=6, display=args.display) as prog:
            prog.update("ensure mongo")
            mongoctl.ensure_mongo_running(_default_mongo_uri(), record_start=True)
            prog.update("bootout legacy")
            for old in [
                "com.wieselquist.wkso",
                "com.wieselquist.wksctl",
                "com.wieselquist.wks",
                "com.wieselquist.wks.db",
            ]:
                try:
                    _launchctl_quiet("bootout", f"gui/{uid}", str(Path.home()/"Library"/"LaunchAgents"/(old+".plist")))
                except Exception:
                    pass
            prog.update("bootstrap")
            _launchctl_quiet("bootstrap", f"gui/{uid}", str(pl))
            prog.update("enable")
            _launchctl_quiet("enable", f"gui/{uid}/com.wieselquist.wkso")
            prog.update("kickstart")
            _launchctl_quiet("kickstart", "-k", f"gui/{uid}/com.wieselquist.wkso")
            prog.update("done")
        print(f"Installed and started: {pl}")

    def daemon_uninstall(args: argparse.Namespace):
        if platform.system() != "Darwin":
            print("uninstall is macOS-only (launchd)")
            return
        pl = _plist_path()
        uid = os.getuid()
        with _make_progress(total=4, display=args.display) as prog:
            for label in ["com.wieselquist.wkso", "com.wieselquist.wksctl", "com.wieselquist.wks", "com.wieselquist.wks.db"]:
                prog.update(f"bootout {label}")
                try:
                    _launchctl_quiet("bootout", f"gui/{uid}", str(Path.home()/"Library"/"LaunchAgents"/(label+".plist")))
                except Exception:
                    pass
                prog.update(f"remove {label}.plist")
                try:
                    (Path.home()/"Library"/"LaunchAgents"/(label+".plist")).unlink()
                except Exception:
                    pass
        _stop_managed_mongo()
        print("Uninstalled.")

    # install/uninstall bound under service group below

    # Single entry for service management
    svc = sub.add_parser("service", help="Install/start/stop the WKS daemon (macOS)")
    svcsub = svc.add_subparsers(dest="svc_cmd")
    svcinst = svcsub.add_parser("install", help="Install launchd agent (macOS)")
    svcinst.set_defaults(func=daemon_install)
    svcrem = svcsub.add_parser("uninstall", help="Uninstall launchd agent (macOS)")
    svcrem.set_defaults(func=daemon_uninstall)
    svcstart2 = svcsub.add_parser("start", help="Start daemon in background or via launchd if installed")
    svcstart2.set_defaults(func=daemon_start)
    svcstop2 = svcsub.add_parser("stop", help="Stop daemon")
    svcstop2.set_defaults(func=daemon_stop)
    svcstatus2 = svcsub.add_parser("status", help="Daemon status")
    svcstatus2.set_defaults(func=daemon_status)
    svcrestart2 = svcsub.add_parser("restart", help="Restart daemon")
    svcrestart2.set_defaults(func=daemon_restart)

    # Service reset: stop agent, reset DB and local state, restart agent
    svcreset = svcsub.add_parser("reset", help="Stop service, reset databases/state, and start service cleanly")
    def _service_reset(args: argparse.Namespace) -> int:
        # Stop current agent (quiet if not running)
        try:
            if platform.system() == "Darwin":
                _launchctl_quiet("bootout", f"gui/{os.getuid()}", str(_plist_path()))
            else:
                daemon_stop(args)
        except Exception:
            pass
        # Reuse DB reset steps
        _db_reset(args)
        _stop_managed_mongo()
        # Ensure Mongo is running again before restart
        try:
            mongoctl.ensure_mongo_running(_default_mongo_uri(), record_start=True)
        except SystemExit:
            return 2
        # Clear local agent state (keep config.json)
        try:
            home = Path.home()
            for name in [
                'file_ops.jsonl','monitor_state.json','activity_state.json','health.json',
                'daemon.lock','daemon.log','daemon.error.log'
            ]:
                p = home/WKS_HOME_EXT/name
                try:
                    if p.exists():
                        p.unlink()
                except Exception:
                    pass
        except Exception:
            pass
        # Start service again
        try:
            if platform.system() == "Darwin":
                pl = _plist_path()
                _launchctl_quiet("bootstrap", f"gui/{os.getuid()}", str(pl))
                _launchctl_quiet("enable", f"gui/{os.getuid()}/com.wieselquist.wkso")
                _launchctl_quiet("kickstart", "-k", f"gui/{os.getuid()}/com.wieselquist.wkso")
            else:
                daemon_start(args)
        except Exception:
            pass
        # Show status and space stats
        try:
            daemon_status(args)
        except Exception:
            pass
        try:
            _db_info(argparse.Namespace(space=True, time=False, latest=5, display=getattr(args,'display','rich')))
        except Exception:
            pass
        return 0
    svcreset.set_defaults(func=_service_reset)

    # Monitor command: filesystem monitoring status and configuration
    mon = sub.add_parser("monitor", help="Filesystem monitoring status and configuration")
    monsub = mon.add_subparsers(dest="monitor_cmd", required=False)

    # monitor status
    monstatus = monsub.add_parser("status", help="Show monitoring statistics")
    def _monitor_status_cmd(args: argparse.Namespace) -> int:
        """Show monitoring statistics."""
        display = args.display_obj

        # Show config location and WKS_HOME
        from .config import wks_home_path
        config_file = wks_home_path() / "config.json"
        display.info(f"Reading config from: {config_file}")

        wks_home_display = os.environ.get("WKS_HOME", str(wks_home_path()))
        display.info(f"WKS_HOME: {wks_home_display}")

        cfg = load_config()

        # Get monitor config
        monitor_config = cfg.get("monitor", {})

        # Get database connection
        mongo_config = cfg.get("mongo", {})
        if not mongo_config:
            mongo_config = cfg.get("db", {})

        mongo_uri = mongo_config.get("uri", "mongodb://localhost:27017/")
        db_name = monitor_config.get("database", "wks")
        coll_name = monitor_config.get("collection", "monitor")

        # Run validation first
        include_paths = set(monitor_config.get("include_paths", []))
        exclude_paths = set(monitor_config.get("exclude_paths", []))
        managed_dirs = set(monitor_config.get("managed_directories", {}).keys())
        ignore_dirnames = monitor_config.get("ignore_dirnames", [])
        ignore_globs = monitor_config.get("ignore_globs", [])

        issues = []  # Inconsistencies (red)
        redundancies = []  # Redundant items (yellow)

        # Check for conflicts
        conflicts = include_paths & exclude_paths
        for path in conflicts:
            issues.append(f"Path in both include_paths and exclude_paths: {path}")

        # Check for duplicate managed directories (nested)
        from pathlib import Path as P
        managed_list = list(managed_dirs)
        for i, dir1 in enumerate(managed_list):
            p1 = P(dir1).expanduser().resolve()
            for dir2 in managed_list[i+1:]:
                p2 = P(dir2).expanduser().resolve()
                try:
                    if p1 == p2:
                        redundancies.append(f"Duplicate managed_directories: {dir1} and {dir2} resolve to same path")
                except:
                    pass

        # Check for redundant ignore_dirnames (matched by ignore_globs)
        for dirname in ignore_dirnames:
            is_valid, error_msg = MonitorValidator.validate_ignore_dirname(dirname, ignore_globs)
            if not is_valid:
                redundancies.append(f"ignore_dirnames entry '{dirname}': {error_msg}")

        # Check for invalid ignore_globs (syntax errors)
        for glob_pattern in ignore_globs:
            is_valid, error_msg = MonitorValidator.validate_ignore_glob(glob_pattern)
            if not is_valid:
                issues.append(f"ignore_globs entry '{glob_pattern}': {error_msg}")

        # Check for managed_directories that would not be monitored
        managed_dirs_dict = monitor_config.get("managed_directories", {})
        for managed_path in managed_dirs_dict.keys():
            is_valid, error_msg = MonitorValidator.validate_managed_directory(
                managed_path,
                list(include_paths),
                list(exclude_paths),
                ignore_dirnames,
                ignore_globs
            )
            if not is_valid:
                issues.append(f"managed_directories entry '{managed_path}' would NOT be monitored: {error_msg}")

        # Check for vault_path in include/exclude paths (vault is automatically ignored)
        vault_path = cfg.get("vault_path")
        if vault_path:
            vault_resolved = str(P(vault_path).expanduser().resolve())

            # Check if vault_path is EXPLICITLY in include_paths (ERROR - exact match only)
            for include_path in include_paths:
                include_resolved = str(P(include_path).expanduser().resolve())
                if vault_resolved == include_resolved:
                    issues.append(f"vault_path '{vault_path}' explicitly in include_paths - vault is automatically ignored")

            # Check if vault_path is in exclude_paths (WARNING - redundant)
            for exclude_path in exclude_paths:
                exclude_resolved = str(P(exclude_path).expanduser().resolve())
                if vault_resolved == exclude_resolved:
                    redundancies.append(f"exclude_paths entry '{exclude_path}' is redundant - vault_path is automatically ignored")

        # Check for ~/.wks and .wkso (automatically ignored system paths)
        wks_home = str(P("~/.wks").expanduser().resolve())

        # Check if ~/.wks is EXPLICITLY in include_paths (ERROR - exact match only)
        for include_path in include_paths:
            include_resolved = str(P(include_path).expanduser().resolve())
            if wks_home == include_resolved:
                issues.append(f"WKS home '~/.wks' explicitly in include_paths - WKS home is automatically ignored")

        # Check if ~/.wks is in exclude_paths (WARNING - redundant)
        for exclude_path in exclude_paths:
            exclude_resolved = str(P(exclude_path).expanduser().resolve())
            if wks_home == exclude_resolved:
                redundancies.append(f"exclude_paths entry '{exclude_path}' is redundant - WKS home is automatically ignored")

        # Check if .wkso is in ignore_dirnames (WARNING - redundant)
        if ".wkso" in ignore_dirnames:
            redundancies.append(f"ignore_dirnames entry '.wkso' is redundant - .wkso directories are automatically ignored")

        # Check if ~/.wks is in managed_directories (ERROR)
        for managed_path in managed_dirs_dict.keys():
            managed_resolved = str(P(managed_path).expanduser().resolve())
            if managed_resolved == wks_home or managed_resolved.startswith(wks_home + "/"):
                issues.append(f"managed_directories entry '{managed_path}' is in WKS home - cannot manage WKS home directory")

        # Connect to MongoDB
        display.status(f"Connecting to {db_name}.{coll_name}...")
        try:
            from pymongo import MongoClient
            client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
            client.server_info()
            db = client[db_name]
            coll = db[coll_name]

            # Get statistics
            total_files = coll.count_documents({})

            managed_dirs_dict = monitor_config.get("managed_directories", {})

            # Build table data
            status_data = [
                {"Setting": "Tracked Files", "Value": str(total_files)},
                {"Setting": "", "Value": ""},
                {"Setting": "managed_directories", "Value": str(len(managed_dirs_dict))},
            ]

            # Build sets of problematic paths for coloring
            red_paths = set()
            yellow_paths = set()
            for issue in issues:
                for path in managed_dirs_dict.keys() | include_paths | exclude_paths:
                    if f"'{path}'" in issue or f" {path}" in issue or issue.endswith(path):
                        red_paths.add(path)

            for redund in redundancies:
                for path in managed_dirs_dict.keys() | include_paths | exclude_paths:
                    if f"'{path}'" in redund or f" {path}" in redund or redund.endswith(path):
                        yellow_paths.add(path)

            # Calculate max pip count and max number width for alignment
            import math
            max_pip_count = 0
            max_num_width = 0
            for priority in managed_dirs_dict.values():
                if priority <= 1:
                    pip_count = 1
                else:
                    pip_count = int(math.log10(priority)) + 1
                max_pip_count = max(max_pip_count, pip_count)
                max_num_width = max(max_num_width, len(str(priority)))

            # Add managed directories with logarithmic pip visualization and validation
            for path, priority in sorted(managed_dirs_dict.items(), key=lambda x: -x[1]):
                # Create logarithmic pip visualization
                # 1 pip for <=1, 2 pips for <10, 3 pips for <100, 4 pips for <1000, etc.
                if priority <= 1:
                    pip_count = 1
                else:
                    pip_count = int(math.log10(priority)) + 1
                pips = "▪" * pip_count

                # Validate that this managed directory would be monitored
                is_valid, error_msg = MonitorValidator.validate_managed_directory(
                    path,
                    list(include_paths),
                    list(exclude_paths),
                    ignore_dirnames,
                    ignore_globs
                )

                # Collect validation messages and get status symbol
                if error_msg:
                    issues.append(f"managed_directories entry '{path}': {error_msg}")
                status_symbol = MonitorValidator.status_symbol(error_msg, is_valid)

                # Left-align pips, right-align numbers, add status symbol
                pips_padded = pips.ljust(max_pip_count)
                num_padded = str(priority).rjust(max_num_width)
                priority_display = f"{pips_padded} {num_padded} {status_symbol}"

                status_data.append({
                    "Setting": f"  {path}",
                    "Value": priority_display
                })

            status_data.append({"Setting": "", "Value": ""})
            status_data.append({"Setting": "include_paths", "Value": str(len(include_paths))})
            for path in sorted(include_paths):
                error_msg = None if path not in (red_paths | yellow_paths) else "issue"
                is_valid = path not in red_paths
                status_data.append({"Setting": f"  {path}", "Value": MonitorValidator.status_symbol(error_msg, is_valid)})

            status_data.append({"Setting": "", "Value": ""})
            status_data.append({"Setting": "exclude_paths", "Value": str(len(exclude_paths))})
            for path in sorted(exclude_paths):
                error_msg = None if path not in (red_paths | yellow_paths) else "issue"
                is_valid = path not in red_paths
                status_data.append({"Setting": f"  {path}", "Value": MonitorValidator.status_symbol(error_msg, is_valid)})

            # Build ignore rules list with validation
            ignore_list = []
            ignore_list.append(("ignore_dirnames", str(len(ignore_dirnames))))
            ignore_list.append(("", ""))

            # Validate each ignore_dirname
            for dirname in ignore_dirnames:
                is_valid, error_msg = MonitorValidator.validate_ignore_dirname(dirname, ignore_globs)
                ignore_list.append((f"  {dirname}", MonitorValidator.status_symbol(error_msg, is_valid)))
                if error_msg:
                    (redundancies if is_valid else issues).append(f"ignore_dirnames entry '{dirname}': {error_msg}")

            ignore_list.append(("", ""))
            ignore_list.append(("ignore_globs", str(len(ignore_globs))))

            # Validate each ignore_glob for syntax errors
            for glob_pattern in ignore_globs:
                is_valid, error_msg = MonitorValidator.validate_ignore_glob(glob_pattern)
                ignore_list.append((f"  {glob_pattern}", MonitorValidator.status_symbol(error_msg, is_valid)))
                if error_msg:
                    (redundancies if is_valid else issues).append(f"ignore_globs pattern '{glob_pattern}': {error_msg}")

            # Combine into single table with 4 columns
            max_rows = max(len(status_data), len(ignore_list))
            combined_data = []

            for i in range(max_rows):
                row = {}
                if i < len(status_data):
                    row["Setting"] = status_data[i]["Setting"]
                    row["Value"] = status_data[i]["Value"]
                else:
                    row["Setting"] = ""
                    row["Value"] = ""

                if i < len(ignore_list):
                    row["Ignore Rule"] = ignore_list[i][0]
                    row["Count"] = ignore_list[i][1]
                else:
                    row["Ignore Rule"] = ""
                    row["Count"] = ""

                combined_data.append(row)

            display.table(
                combined_data,
                headers=["Setting", "Value", "Ignore Rule", "Count"],
                title="Monitor Status",
                column_justify={"Value": "right", "Count": "right"}
            )

            # Print issues and redundancies
            if issues:
                display.error(f"\nInconsistencies found ({len(issues)}):")
                for issue in issues:
                    display.error(f"  • {issue}")

            if redundancies:
                display.warning(f"\nRedundancies found ({len(redundancies)}):")
                for redund in redundancies:
                    display.warning(f"  • {redund}")

            if not issues and not redundancies:
                display.success("\n✓ No configuration issues found")

            client.close()
            return 0

        except Exception as e:
            display.error(f"Failed to get monitor status: {e}")
            return 2

    monstatus.set_defaults(func=_monitor_status_cmd)

    # monitor validate - check for inconsistencies
    monvalidate = monsub.add_parser("validate", help="Check for configuration inconsistencies")
    def _monitor_validate_cmd(args: argparse.Namespace) -> int:
        """Check for configuration inconsistencies."""
        display = args.display_obj
        cfg = load_config()
        monitor_config = cfg.get("monitor", {})

        include_paths = set(monitor_config.get("include_paths", []))
        exclude_paths = set(monitor_config.get("exclude_paths", []))
        managed_dirs = set(monitor_config.get("managed_directories", {}).keys())

        issues = []
        warnings = []

        # Check 1: Paths in both include and exclude
        conflicts = include_paths & exclude_paths
        if conflicts:
            for path in conflicts:
                issues.append(f"Path in both include and exclude: {path}")

        # Check 2: Duplicate managed directories (same resolved path)
        from pathlib import Path as P
        managed_list = list(managed_dirs)
        for i, dir1 in enumerate(managed_list):
            p1 = P(dir1).expanduser().resolve()
            for dir2 in managed_list[i+1:]:
                p2 = P(dir2).expanduser().resolve()
                try:
                    if p1 == p2:
                        warnings.append(f"Duplicate managed directories: {dir1} and {dir2} resolve to same path")
                except:
                    pass

        # Display results
        if not issues and not warnings:
            display.success("No configuration issues found")
            return 0

        if issues:
            display.error(f"Found {len(issues)} error(s):")
            for issue in issues:
                display.error(f"  • {issue}")

        if warnings:
            display.warning(f"Found {len(warnings)} warning(s):")
            for warning in warnings:
                display.warning(f"  • {warning}")

        return 1 if issues else 0

    monvalidate.set_defaults(func=_monitor_validate_cmd)

    # monitor check - test if a path would be monitored
    moncheck = monsub.add_parser("check", help="Check if a path would be monitored")
    moncheck.add_argument("path", help="Path to check")
    def _monitor_check_cmd(args: argparse.Namespace) -> int:
        """Check if a path would be monitored."""
        display = args.display_obj
        cfg = load_config()
        monitor_config = cfg.get("monitor", {})

        # Get configuration
        include_paths = monitor_config.get("include_paths", [])
        exclude_paths = monitor_config.get("exclude_paths", [])
        ignore_dirnames = monitor_config.get("ignore_dirnames", [])
        ignore_globs = monitor_config.get("ignore_globs", [])
        managed_dirs = monitor_config.get("managed_directories", {})
        priority_config = monitor_config.get("priority", {})

        # Resolve path
        from pathlib import Path as P
        test_path = P(args.path).expanduser().resolve()

        # Build decision chain
        decisions = []
        is_monitored = True
        reason = None
        priority = None

        # Step 1: Check if path exists (informational)
        if test_path.exists():
            decisions.append(("✓", f"Path exists: {test_path}"))
        else:
            decisions.append(("⚠", f"Path does not exist (checking as if it did): {test_path}"))

        # Step 2: Check include_paths
        included = False
        for include_path in include_paths:
            include_resolved = P(include_path).expanduser().resolve()
            try:
                # Check if test_path is under include_path
                test_path.relative_to(include_resolved)
                included = True
                decisions.append(("✓", f"Matches include_paths: {include_path}"))
                break
            except ValueError:
                continue

        if not included:
            is_monitored = False
            reason = "Not under any include_paths"
            decisions.append(("✗", reason))

        # Step 3: Check exclude_paths
        if is_monitored:
            for exclude_path in exclude_paths:
                exclude_resolved = P(exclude_path).expanduser().resolve()
                try:
                    test_path.relative_to(exclude_resolved)
                    is_monitored = False
                    reason = f"Matches exclude_paths: {exclude_path}"
                    decisions.append(("✗", reason))
                    break
                except ValueError:
                    continue

            if is_monitored:
                decisions.append(("✓", "Not in exclude_paths"))

        # Step 4: Check ignore_dirnames
        if is_monitored:
            path_parts = test_path.parts
            for part in path_parts:
                if part in ignore_dirnames:
                    is_monitored = False
                    reason = f"Directory name '{part}' in ignore_dirnames"
                    decisions.append(("✗", reason))
                    break

            if is_monitored:
                decisions.append(("✓", "No directory names match ignore_dirnames"))

        # Step 5: Check ignore_globs
        if is_monitored:
            import fnmatch
            matched_glob = None
            for glob_pattern in ignore_globs:
                # Check against full path
                if fnmatch.fnmatch(str(test_path), glob_pattern):
                    matched_glob = glob_pattern
                    break
                # Check against filename only
                if fnmatch.fnmatch(test_path.name, glob_pattern):
                    matched_glob = glob_pattern
                    break

            if matched_glob:
                is_monitored = False
                reason = f"Matches ignore_globs: {matched_glob}"
                decisions.append(("✗", reason))
            else:
                decisions.append(("✓", "Does not match ignore_globs"))

        # Step 6: Calculate priority if monitored
        if is_monitored:
            from wks.priority import calculate_priority
            priority = calculate_priority(test_path, managed_dirs, priority_config)
            decisions.append(("✓", f"Priority score: {priority}"))

            # Show which managed directory matched
            from wks.priority import find_managed_directory
            matched_dir, base_priority = find_managed_directory(test_path, managed_dirs)
            if matched_dir:
                decisions.append(("ℹ", f"Managed directory: {matched_dir} (base priority {base_priority})"))

        # Display results
        if is_monitored:
            display.success(f"Path WOULD be monitored: {test_path}")
            if priority:
                display.info(f"Priority: {priority}")
        else:
            display.error(f"Path would NOT be monitored: {test_path}")
            if reason:
                display.error(f"Reason: {reason}")

        # Show decision chain
        display.info("\nDecision chain:")
        for symbol, message in decisions:
            if symbol == "✓":
                display.success(f"  {message}")
            elif symbol == "✗":
                display.error(f"  {message}")
            elif symbol == "⚠":
                display.warning(f"  {message}")
            else:
                display.info(f"  {message}")

        return 0 if is_monitored else 1

    moncheck.set_defaults(func=_monitor_check_cmd)

    # Helper classes for monitor validation
    class MonitorValidator:
        """Encapsulates monitor configuration validation logic."""

        @staticmethod
        def status_symbol(error_msg: Optional[str], is_valid: bool = True) -> str:
            """Convert validation result to colored status symbol."""
            return "[green]✓[/]" if not error_msg else "[yellow]⚠[/]" if is_valid else "[red]✗[/]"

        @staticmethod
        def validate_ignore_dirname(dirname: str, ignore_globs: List[str]) -> Tuple[bool, Optional[str]]:
            """Validate an ignore_dirname entry."""
            import fnmatch
            if '*' in dirname or '?' in dirname or '[' in dirname:
                return False, "ignore_dirnames cannot contain wildcard characters (*, ?, [). Use ignore_globs for patterns."
            for glob_pattern in ignore_globs:
                if fnmatch.fnmatch(dirname, glob_pattern):
                    return True, f"Redundant: dirname '{dirname}' already matched by ignore_globs pattern '{glob_pattern}'"
            return True, None

        @staticmethod
        def validate_ignore_glob(pattern: str) -> Tuple[bool, Optional[str]]:
            """Validate an ignore_glob pattern for syntax errors."""
            import fnmatch
            try:
                fnmatch.fnmatch("test", pattern)
                return True, None
            except Exception as e:
                return False, f"Invalid glob syntax: {str(e)}"

        @staticmethod
        def validate_managed_directory(managed_path: str, include_paths: List[str],
                                     exclude_paths: List[str], ignore_dirnames: List[str],
                                     ignore_globs: List[str]) -> Tuple[bool, Optional[str]]:
            """Validate that a managed_directory would actually be monitored."""
            from pathlib import Path as P
            import fnmatch

            managed_resolved = P(managed_path).expanduser().resolve()

            # Check for system paths that are always ignored
            wks_home = P("~/.wks").expanduser().resolve()
            if managed_resolved == wks_home or str(managed_resolved).startswith(str(wks_home) + "/"):
                return False, "In WKS home directory (automatically ignored)"

            if ".wkso" in managed_resolved.parts:
                return False, "Contains .wkso directory (automatically ignored)"

            # Check if under any include_paths
            if not any(managed_resolved.is_relative_to(P(p).expanduser().resolve())
                      for p in include_paths):
                return False, "Not under any include_paths"

            # Check if in exclude_paths
            for exclude_path in exclude_paths:
                try:
                    if managed_resolved.is_relative_to(P(exclude_path).expanduser().resolve()):
                        return False, f"Matched by exclude_paths: {exclude_path}"
                except:
                    pass

            # Check if any path component matches ignore_dirnames
            for part in managed_resolved.parts:
                if part in ignore_dirnames:
                    return False, f"Contains ignored dirname: {part}"

            # Check if matches ignore_globs
            for glob_pattern in ignore_globs:
                if fnmatch.fnmatch(str(managed_resolved), glob_pattern) or \
                   fnmatch.fnmatch(managed_resolved.name, glob_pattern):
                    return False, f"Matched by ignore_globs: {glob_pattern}"

            return True, None

    # Helper function for modifying config lists

    def _modify_monitor_list(display, list_name: str, value: str, operation: str, resolve_path: bool = True) -> int:
        """Modify a monitor config list (add/remove)."""
        from .config import wks_home_path
        config_path = wks_home_path() / "config.json"

        if not config_path.exists():
            display.error(f"Config file not found: {config_path}")
            return 2

        # Read current config
        with open(config_path) as f:
            cfg = json.load(f)

        # Get monitor section
        if "monitor" not in cfg:
            cfg["monitor"] = {}

        if list_name not in cfg["monitor"]:
            cfg["monitor"][list_name] = []

        # Normalize path for comparison if needed
        if resolve_path:
            # Resolve the input path
            value_resolved = str(Path(value).expanduser().resolve())

            # Preserve tilde notation if the resolved path is in home directory
            home_dir = str(Path.home())
            if value_resolved.startswith(home_dir):
                value_to_store = "~" + value_resolved[len(home_dir):]
            else:
                value_to_store = value_resolved

            # Find if this path exists in the list (comparing resolved versions)
            existing_entry = None
            for entry in cfg["monitor"][list_name]:
                entry_resolved = str(Path(entry).expanduser().resolve())
                if entry_resolved == value_resolved:
                    existing_entry = entry
                    break
        else:
            value_resolved = value
            value_to_store = value
            existing_entry = value if value in cfg["monitor"][list_name] else None

        # Perform operation
        if operation == "add":
            # Validate ignore_dirnames before adding
            if list_name == "ignore_dirnames":
                ignore_globs = cfg["monitor"].get("ignore_globs", [])
                is_valid, error_msg = MonitorValidator.validate_ignore_dirname(value_resolved if not resolve_path else value, ignore_globs)
                if not is_valid:
                    display.error(error_msg)
                    return 1

            if existing_entry:
                display.warning(f"Already in {list_name}: {existing_entry}")
                return 0

            # Store using tilde notation when possible
            cfg["monitor"][list_name].append(value_to_store)
            display.success(f"Added to {list_name}: {value_to_store}")
        elif operation == "remove":
            if not existing_entry:
                display.warning(f"Not in {list_name}: {value}")
                return 0
            cfg["monitor"][list_name].remove(existing_entry)
            display.success(f"Removed from {list_name}: {existing_entry}")

        # Write back
        with open(config_path, "w") as f:
            json.dump(cfg, f, indent=4)

        display.info("Restart the monitor service for changes to take effect")
        return 0

    # Helper function to show a list
    def _show_monitor_list(display, list_name: str, title: str) -> int:
        """Show contents of a monitor config list with validation status."""
        cfg = load_config()
        monitor_config = cfg.get("monitor", {})
        items = monitor_config.get(list_name, [])

        if not items:
            display.info(f"No {list_name} configured")
            return 0

        # Get other config items for validation
        ignore_globs = monitor_config.get("ignore_globs", [])
        ignore_dirnames = monitor_config.get("ignore_dirnames", [])
        include_paths = monitor_config.get("include_paths", [])
        exclude_paths = monitor_config.get("exclude_paths", [])
        managed_dirs = monitor_config.get("managed_directories", {})

        from pathlib import Path as P

        table_data = []
        for i, item in enumerate(items, 1):
            is_valid, error_msg = True, None

            if list_name == "ignore_dirnames":
                is_valid, error_msg = MonitorValidator.validate_ignore_dirname(item, ignore_globs)
            elif list_name == "ignore_globs":
                is_valid, error_msg = MonitorValidator.validate_ignore_glob(item)
            elif list_name in ("include_paths", "exclude_paths"):
                try:
                    path_obj = P(item).expanduser().resolve()
                    if not path_obj.exists():
                        is_valid = list_name == "exclude_paths"  # Warning for exclude, error for include
                        error_msg = "Path does not exist" + (" (will be ignored if created)" if is_valid else "")
                    elif not path_obj.is_dir():
                        is_valid, error_msg = False, "Not a directory"
                except Exception as e:
                    is_valid, error_msg = False, f"Invalid path: {e}"

            table_data.append({"#": str(i), "Value": item, "Status": MonitorValidator.status_symbol(error_msg, is_valid)})

        display.table(table_data, title=title)
        return 0

    # monitor include_paths add/remove/list
    mon_include = monsub.add_parser("include_paths", help="Manage include_paths")
    mon_include_sub = mon_include.add_subparsers(dest="include_paths_op", required=False)

    # Default action: show list
    def _monitor_include_default(args: argparse.Namespace) -> int:
        if not args.include_paths_op:
            return _show_monitor_list(args.display_obj, "include_paths", "Include Paths")
        return 0
    mon_include.set_defaults(func=_monitor_include_default)

    mon_include_add = mon_include_sub.add_parser("add", help="Add path(s) to include_paths")
    mon_include_add.add_argument("paths", nargs='+', help="Path(s) to monitor")
    def _monitor_include_add(args: argparse.Namespace) -> int:
        for path in args.paths:
            result = _modify_monitor_list(args.display_obj, "include_paths", path, "add", resolve_path=True)
            if result != 0:
                return result
        return 0
    mon_include_add.set_defaults(func=_monitor_include_add)

    mon_include_remove = mon_include_sub.add_parser("remove", help="Remove path(s) from include_paths")
    mon_include_remove.add_argument("paths", nargs='+', help="Path(s) to remove")
    def _monitor_include_remove(args: argparse.Namespace) -> int:
        for path in args.paths:
            result = _modify_monitor_list(args.display_obj, "include_paths", path, "remove", resolve_path=True)
            if result != 0:
                return result
        return 0
    mon_include_remove.set_defaults(func=_monitor_include_remove)

    # monitor exclude_paths add/remove
    mon_exclude = monsub.add_parser("exclude_paths", help="Manage exclude_paths")
    mon_exclude_sub = mon_exclude.add_subparsers(dest="exclude_paths_op", required=False)

    def _monitor_exclude_default(args: argparse.Namespace) -> int:
        if not args.exclude_paths_op:
            return _show_monitor_list(args.display_obj, "exclude_paths", "Exclude Paths")
        return 0
    mon_exclude.set_defaults(func=_monitor_exclude_default)

    mon_exclude_add = mon_exclude_sub.add_parser("add", help="Add path(s) to exclude_paths")
    mon_exclude_add.add_argument("paths", nargs='+', help="Path(s) to exclude")
    def _monitor_exclude_add(args: argparse.Namespace) -> int:
        for path in args.paths:
            result = _modify_monitor_list(args.display_obj, "exclude_paths", path, "add", resolve_path=True)
            if result != 0:
                return result
        return 0
    mon_exclude_add.set_defaults(func=_monitor_exclude_add)

    mon_exclude_remove = mon_exclude_sub.add_parser("remove", help="Remove path(s) from exclude_paths")
    mon_exclude_remove.add_argument("paths", nargs='+', help="Path(s) to remove")
    def _monitor_exclude_remove(args: argparse.Namespace) -> int:
        for path in args.paths:
            result = _modify_monitor_list(args.display_obj, "exclude_paths", path, "remove", resolve_path=True)
            if result != 0:
                return result
        return 0
    mon_exclude_remove.set_defaults(func=_monitor_exclude_remove)

    # monitor ignore_dirnames add/remove
    mon_ignore_dir = monsub.add_parser("ignore_dirnames", help="Manage ignore_dirnames")
    mon_ignore_dir_sub = mon_ignore_dir.add_subparsers(dest="ignore_dirnames_op", required=False)

    def _monitor_ignore_dir_default(args: argparse.Namespace) -> int:
        if not args.ignore_dirnames_op:
            return _show_monitor_list(args.display_obj, "ignore_dirnames", "Ignore Directory Names")
        return 0
    mon_ignore_dir.set_defaults(func=_monitor_ignore_dir_default)

    mon_ignore_dir_add = mon_ignore_dir_sub.add_parser("add", help="Add directory name(s) to ignore_dirnames")
    mon_ignore_dir_add.add_argument("dirnames", nargs='+', help="Directory name(s) to ignore (e.g., node_modules)")
    def _monitor_ignore_dir_add(args: argparse.Namespace) -> int:
        for dirname in args.dirnames:
            result = _modify_monitor_list(args.display_obj, "ignore_dirnames", dirname, "add", resolve_path=False)
            if result != 0:
                return result
        return 0
    mon_ignore_dir_add.set_defaults(func=_monitor_ignore_dir_add)

    mon_ignore_dir_remove = mon_ignore_dir_sub.add_parser("remove", help="Remove directory name(s) from ignore_dirnames")
    mon_ignore_dir_remove.add_argument("dirnames", nargs='+', help="Directory name(s) to remove")
    def _monitor_ignore_dir_remove(args: argparse.Namespace) -> int:
        for dirname in args.dirnames:
            result = _modify_monitor_list(args.display_obj, "ignore_dirnames", dirname, "remove", resolve_path=False)
            if result != 0:
                return result
        return 0
    mon_ignore_dir_remove.set_defaults(func=_monitor_ignore_dir_remove)

    # monitor ignore_globs add/remove
    mon_ignore_glob = monsub.add_parser("ignore_globs", help="Manage ignore_globs")
    mon_ignore_glob_sub = mon_ignore_glob.add_subparsers(dest="ignore_globs_op", required=False)

    def _monitor_ignore_glob_default(args: argparse.Namespace) -> int:
        if not args.ignore_globs_op:
            return _show_monitor_list(args.display_obj, "ignore_globs", "Ignore Glob Patterns")
        return 0
    mon_ignore_glob.set_defaults(func=_monitor_ignore_glob_default)

    mon_ignore_glob_add = mon_ignore_glob_sub.add_parser("add", help="Add glob pattern(s) to ignore_globs")
    mon_ignore_glob_add.add_argument("patterns", nargs='+', help="Glob pattern(s) to ignore (e.g., *.tmp)")
    def _monitor_ignore_glob_add(args: argparse.Namespace) -> int:
        for pattern in args.patterns:
            result = _modify_monitor_list(args.display_obj, "ignore_globs", pattern, "add", resolve_path=False)
            if result != 0:
                return result
        return 0
    mon_ignore_glob_add.set_defaults(func=_monitor_ignore_glob_add)

    mon_ignore_glob_remove = mon_ignore_glob_sub.add_parser("remove", help="Remove glob pattern(s) from ignore_globs")
    mon_ignore_glob_remove.add_argument("patterns", nargs='+', help="Pattern(s) to remove")
    def _monitor_ignore_glob_remove(args: argparse.Namespace) -> int:
        for pattern in args.patterns:
            result = _modify_monitor_list(args.display_obj, "ignore_globs", pattern, "remove", resolve_path=False)
            if result != 0:
                return result
        return 0
    mon_ignore_glob_remove.set_defaults(func=_monitor_ignore_glob_remove)

    # monitor managed add/remove/set-priority
    mon_managed = monsub.add_parser("managed", help="Manage managed_directories with priorities")
    mon_managed_sub = mon_managed.add_subparsers(dest="managed_op", required=False)

    def _monitor_managed_default(args: argparse.Namespace) -> int:
        if not args.managed_op:
            cfg = load_config()
            monitor_config = cfg.get("monitor", {})
            managed_dirs = monitor_config.get("managed_directories", {})

            if not managed_dirs:
                args.display_obj.info("No managed_directories configured")
                return 0

            table_data = []
            for path, priority in sorted(managed_dirs.items(), key=lambda x: -x[1]):
                table_data.append({"Path": path, "Priority": str(priority)})

            args.display_obj.table(table_data, title="Managed Directories")
            return 0
        return 0
    mon_managed.set_defaults(func=_monitor_managed_default)

    mon_managed_add = mon_managed_sub.add_parser("add", help="Add managed directory with priority")
    mon_managed_add.add_argument("path", help="Directory path")
    mon_managed_add.add_argument("--priority", type=int, required=True, help="Priority score (e.g., 100)")
    def _monitor_managed_add(args: argparse.Namespace) -> int:
        from .config import wks_home_path
        config_path = wks_home_path() / "config.json"

        if not config_path.exists():
            args.display_obj.error(f"Config file not found: {config_path}")
            return 2

        path = str(Path(args.path).expanduser().resolve())

        with open(config_path) as f:
            cfg = json.load(f)

        if "monitor" not in cfg:
            cfg["monitor"] = {}
        if "managed_directories" not in cfg["monitor"]:
            cfg["monitor"]["managed_directories"] = {}

        cfg["monitor"]["managed_directories"][path] = args.priority

        with open(config_path, "w") as f:
            json.dump(cfg, f, indent=4)

        args.display_obj.success(f"Added managed directory: {path} (priority {args.priority})")
        args.display_obj.info("Restart the monitor service for changes to take effect")
        return 0
    mon_managed_add.set_defaults(func=_monitor_managed_add)

    mon_managed_remove = mon_managed_sub.add_parser("remove", help="Remove managed directory")
    mon_managed_remove.add_argument("path", help="Directory path to remove")
    def _monitor_managed_remove(args: argparse.Namespace) -> int:
        from .config import wks_home_path
        config_path = wks_home_path() / "config.json"

        if not config_path.exists():
            args.display_obj.error(f"Config file not found: {config_path}")
            return 2

        path = str(Path(args.path).expanduser().resolve())

        with open(config_path) as f:
            cfg = json.load(f)

        if "monitor" not in cfg or "managed_directories" not in cfg["monitor"]:
            args.display_obj.warning("No managed_directories configured")
            return 0

        if path not in cfg["monitor"]["managed_directories"]:
            args.display_obj.warning(f"Not a managed directory: {path}")
            return 0

        del cfg["monitor"]["managed_directories"][path]

        with open(config_path, "w") as f:
            json.dump(cfg, f, indent=4)

        args.display_obj.success(f"Removed managed directory: {path}")
        args.display_obj.info("Restart the monitor service for changes to take effect")
        return 0
    mon_managed_remove.set_defaults(func=_monitor_managed_remove)

    mon_managed_priority = mon_managed_sub.add_parser("set-priority", help="Set priority for managed directory")
    mon_managed_priority.add_argument("path", help="Directory path")
    mon_managed_priority.add_argument("priority", type=int, help="New priority score")
    def _monitor_managed_priority(args: argparse.Namespace) -> int:
        from .config import wks_home_path
        config_path = wks_home_path() / "config.json"

        if not config_path.exists():
            args.display_obj.error(f"Config file not found: {config_path}")
            return 2

        path = str(Path(args.path).expanduser().resolve())

        with open(config_path) as f:
            cfg = json.load(f)

        if "monitor" not in cfg or "managed_directories" not in cfg["monitor"]:
            args.display_obj.error("No managed_directories configured")
            return 2

        if path not in cfg["monitor"]["managed_directories"]:
            args.display_obj.error(f"Not a managed directory: {path}")
            return 2

        old_priority = cfg["monitor"]["managed_directories"][path]
        cfg["monitor"]["managed_directories"][path] = args.priority

        with open(config_path, "w") as f:
            json.dump(cfg, f, indent=4)

        args.display_obj.success(f"Updated priority: {path} ({old_priority} → {args.priority})")
        args.display_obj.info("Restart the monitor service for changes to take effect")
        return 0
    mon_managed_priority.set_defaults(func=_monitor_managed_priority)

    # Extract text without indexing
    extp = sub.add_parser("extract", help="Extract document text using the configured pipeline")
    extp.add_argument("paths", nargs="+", help="Files or directories to extract")
    def _extract_cmd(args: argparse.Namespace) -> int:
        cfg = load_config()
        include_exts = [e.lower() for e in (cfg.get('similarity', {}).get('include_extensions') or [])]
        files = _iter_files(args.paths, include_exts, cfg)
        if not files:
            print("No files to extract (check paths/extensions)")
            return 0
        extractor = _build_extractor(cfg)
        extracted = 0
        skipped = 0
        errors = 0
        outputs: List[Tuple[Path, Path]] = []
        with _make_progress(total=len(files), display=args.display) as prog:
            for f in files:
                prog.update(f.name, advance=0)
                try:
                    result = extractor.extract(f, persist=True)
                    if result.content_path:
                        extracted += 1
                        outputs.append((f, Path(result.content_path)))
                    else:
                        skipped += 1
                except Exception:
                    errors += 1
                finally:
                    prog.update(f.name, advance=1)
        for src, artefact in outputs:
            print(f"{src} -> {artefact}")
        print(f"Extracted {extracted} file(s), skipped {skipped}, errors {errors}")
        return 0
    extp.set_defaults(func=_extract_cmd)

    # Top-level index command (moved out of analyze)
    idx = sub.add_parser("index", help="Index files or directories (recursive) into similarity DB with progress")
    idx.add_argument("--untrack", action="store_true", help="Remove tracked entries (and artefacts) instead of indexing")
    idx.add_argument("paths", nargs="+", help="Files or directories to process")
    def _index_cmd(args: argparse.Namespace) -> int:
        cfg = load_config()
        include_exts = [e.lower() for e in (cfg.get('similarity', {}).get('include_extensions') or [])]
        files = _iter_files(args.paths, include_exts, cfg)
        if not files:
            print("No files to process (check paths/extensions)")
            return 0

        display_mode = args.display

        if args.untrack:
            removed = 0
            missing = 0
            errors = 0
            outcomes: List[Dict[str, Any]] = []
            with _make_progress(total=len(files), display=args.display) as prog:
                prog.update("Connecting to DB…", advance=0)
                db, _ = _load_similarity_required()
                for f in files:
                    prog.update(f"{f.name} • untrack", advance=0)
                    try:
                        if db.remove_file(f):
                            removed += 1
                            outcomes.append({"path": str(f), "status": "removed"})
                        else:
                            missing += 1
                            outcomes.append({"path": str(f), "status": "not_tracked"})
                    except Exception as exc:
                        errors += 1
                        outcomes.append({"path": str(f), "status": f"error: {exc}"})
                    finally:
                        prog.update(f.name, advance=1)
                prog.update("Untracking complete", advance=0)
            payload = {
                "mode": "untrack",
                "requested": [str(p) for p in files],
                "removed": removed,
                "missing": missing,
                "errors": errors,
                "files": outcomes,
            }
            _maybe_write_json(args, payload)
            print(f"Untracked {removed} file(s), missing {missing}, errors {errors}")
            return 0

        hash_times: Dict[Path, Optional[float]] = {}
        checksums: Dict[Path, Optional[str]] = {}
        file_sizes: Dict[Path, Optional[int]] = {}
        for f in files:
            try:
                h_start = time.perf_counter()
                checksum = _file_checksum(f)
                hash_times[f] = time.perf_counter() - h_start
                checksums[f] = checksum
            except Exception:
                hash_times[f] = None
                checksums[f] = None
            try:
                file_sizes[f] = f.stat().st_size
            except Exception:
                file_sizes[f] = None

        pre_skipped: List[Path] = []
        files_to_process = list(files)
        try:
            client, mongo_cfg = _mongo_client_params(
                server_timeout=300,
                connect_timeout=300,
                cfg=cfg,
                ensure_running=False,
            )
        except Exception:
            client = None
            mongo_cfg = None
        if client is not None and mongo_cfg is not None:
            try:
                coll = client[mongo_cfg['space_database']][mongo_cfg['space_collection']]
                to_process: List[Path] = []
                for f in files:
                    checksum = checksums.get(f)
                    if checksum is None:
                        to_process.append(f)
                        continue
                    doc = coll.find_one({"path": _as_file_uri_local(f)})
                    try:
                        record_db_activity("index.precheck", str(f))
                    except Exception:
                        pass
                    if not doc:
                        doc = coll.find_one({"path_local": str(f.resolve())})
                    if doc and doc.get("checksum") == checksum:
                        pre_skipped.append(f)
                    else:
                        to_process.append(f)
                files_to_process = to_process
            finally:
                try:
                    client.close()
                except Exception:
                    pass

        def _fmt_duration(seconds: Optional[float]) -> str:
            if seconds is None:
                return "—"
            if seconds >= 1:
                return f"{seconds:6.2f} {'s':>2}"
            return f"{seconds * 1000:6.1f} {'ms':>2}"

        stage_labels = [
            ("hash", "Hash"),
            ("extract", "Extract"),
            ("embed", "Embed"),
            ("db", "DB"),
            ("chunks", "Chunks"),
            ("obsidian", "Obsidian"),
        ]

        def _truncate_cell(text: str, limit: Optional[int]) -> str:
            if limit is None or limit <= 0 or len(text) <= limit:
                return text
            if limit == 1:
                return text[:1]
            return text[: limit - 1] + "…"

        def _format_cell(text: str, width: int, align: str) -> str:
            if align == "right":
                return text.rjust(width)
            if align == "center":
                return text.center(width)
            return text.ljust(width)

        def _render_plain_boxed_table(
            title: str,
            header: List[str],
            rows: List[List[str]],
            align: List[str],
            limits: Optional[Dict[int, int]] = None,
        ) -> None:
            if not rows:
                return
            limits = limits or {}
            processed: List[List[str]] = []
            for row in rows:
                processed_row: List[str] = []
                for idx, cell in enumerate(row):
                    text = str(cell)
                    text = _truncate_cell(text, limits.get(idx))
                    processed_row.append(text)
                processed.append(processed_row)
            widths: List[int] = []
            for idx, head in enumerate(header):
                col_width = len(str(head))
                for row in processed:
                    col_width = max(col_width, len(row[idx]))
                limit = limits.get(idx)
                if limit:
                    col_width = min(col_width, limit)
                widths.append(col_width)
            total_width = sum(widths) + 3 * (len(widths) - 1)
            border = "+" + "-" * (total_width + 2) + "+"
            print()
            print(border)
            print("| " + title.center(total_width) + " |")
            print(border)
            header_line = " | ".join(
                _format_cell(str(head), widths[idx], "center" if align[idx] == "right" else align[idx])
                for idx, head in enumerate(header)
            )
            print("| " + header_line + " |")
            separator = "-+-".join("-" * width for width in widths)
            print("| " + separator + " |")
            for row in processed:
                line = " | ".join(
                    _format_cell(cell, widths[idx], align[idx]) for idx, cell in enumerate(row)
                )
                print("| " + line + " |")
            print(border)

        def _render_timing_summary(entries: List[Dict[str, Any]], display_mode: str, fmt) -> None:
            if not entries:
                return
            if display_mode == "none":
                return
            totals: Dict[str, float] = {key: 0.0 for key, _ in stage_labels}
            counts: Dict[str, int] = {key: 0 for key, _ in stage_labels}
            for entry in entries:
                for key, _ in stage_labels:
                    val = entry.get(key)
                    if isinstance(val, (int, float)):
                        totals[key] += val
                        counts[key] += 1

            use_rich = display_mode in {"rich", "plain"}

            if use_rich:
                try:
                    from rich import box
                    from rich.console import Console
                    from rich.panel import Panel
                    from rich.table import Table
                except Exception:
                    use_rich = False
                if use_rich:
                    console = Console(
                        force_terminal=True,
                        color_system=None if display_mode == "rich" else "standard",
                        markup=(display_mode == "rich"),
                        highlight=False,
                        soft_wrap=False,
                    )
                    console.print()
                    detail = Table(
                        show_header=True,
                        header_style="bold" if display_mode == "rich" else "",
                        expand=False,
                        box=box.SQUARE if display_mode == "rich" else box.SIMPLE,
                        pad_edge=False,
                    )
                    detail.add_column("#", justify="right", no_wrap=True, overflow="ignore", min_width=2, max_width=3)
                    detail.add_column(
                        "File",
                        style="cyan" if display_mode == "rich" else "",
                        no_wrap=False,
                        overflow="fold",
                        min_width=12,
                        max_width=28,
                    )
                    detail.add_column(
                        "Status",
                        style="magenta" if display_mode == "rich" else "",
                        no_wrap=False,
                        overflow="fold",
                        min_width=8,
                        max_width=20,
                    )
                    for _, label in stage_labels:
                        detail.add_column(label, justify="right", no_wrap=True, overflow="ignore", min_width=9, max_width=11)
                    for idx, entry in enumerate(entries, 1):
                        row = [str(idx), entry['path'].name, entry['status']]
                        for key, _ in stage_labels:
                            row.append(fmt(entry.get(key)))
                        detail.add_row(*row)
                    total_files = 0
                    for value in counts.values():
                        if value > total_files:
                            total_files = value
                    if not total_files:
                        total_files = len(entries)
                    total_row = ["-", "Totals", f"{total_files} file(s)"]
                    for key, _ in stage_labels:
                        total_row.append(fmt(totals[key] if counts.get(key) else None))
                    detail.add_row(*total_row, style="bold")
                    width = console.width or 80
                    console.print(Panel.fit(detail, title="Timing Details", border_style="dim"), width=min(max(width, 72), 110))
                    return

            header = ["#", "File", "Status"] + [label for _, label in stage_labels]
            align = ["right", "left", "left"] + ["right"] * len(stage_labels)
            limits = {1: 32, 2: 20}
            details_rows: List[List[str]] = []
            for idx, entry in enumerate(entries, 1):
                row = [str(idx), entry['path'].name, entry['status']]
                for key, _ in stage_labels:
                    row.append(fmt(entry.get(key)))
                details_rows.append(row)
            total_files_plain = 0
            for value in counts.values():
                if value > total_files_plain:
                    total_files_plain = value
            if not total_files_plain:
                total_files_plain = len(entries)
            totals_row = ["-", "Totals", f"{total_files_plain} file(s)"]
            for key, _ in stage_labels:
                totals_row.append(fmt(totals[key] if counts.get(key) else None))
            details_rows.append(totals_row)
            _render_plain_boxed_table("Timing Details", header, details_rows, align, limits)
            return

        if not files_to_process:
            skipped = len(pre_skipped)
            total_files = None
            db_summary: Optional[Dict[str, Any]] = None
            try:
                client, mongo_cfg = _mongo_client_params(
                    server_timeout=300,
                    connect_timeout=300,
                    cfg=cfg,
                    ensure_running=False,
                )
                coll = client[mongo_cfg['space_database']][mongo_cfg['space_collection']]
                total_files = coll.count_documents({})
                db_summary = {
                    "database": mongo_cfg['space_database'],
                    "collection": mongo_cfg['space_collection'],
                    "total_files": total_files,
                }
            except Exception:
                db_summary = None
            finally:
                if client is not None:
                    try:
                        client.close()
                    except Exception:
                        pass

            cached_summaries = [
                {
                    "path": f,
                    "status": "cached",
                    "hash": hash_times.get(f),
                    "extract": None,
                    "embed": None,
                    "db": None,
                    "chunks": None,
                    "obsidian": None,
                }
                for f in pre_skipped
            ]

            payload = {
                "mode": "index",
                "requested": [str(p) for p in files],
                "added": 0,
                "skipped": skipped,
                "errors": 0,
                "files": [
                    {
                        "path": str(entry["path"]),
                        "status": entry["status"],
                        "timings": {
                            "hash": entry.get("hash"),
                            "extract": entry.get("extract"),
                            "embed": entry.get("embed"),
                            "db": entry.get("db"),
                            "chunks": entry.get("chunks"),
                            "obsidian": entry.get("obsidian"),
                        },
                    }
                    for entry in cached_summaries
                ],
            }
            if db_summary:
                payload["database"] = db_summary
            _maybe_write_json(args, payload)

            print("Nothing to index; all files already current.")
            print(f"Indexed 0 file(s), skipped {skipped}, errors 0")
            if db_summary:
                print(
                    f"DB: {db_summary['database']}.{db_summary['collection']} total_files={db_summary['total_files']}"
                )
            if cached_summaries:
                _render_timing_summary(cached_summaries, display_mode, _fmt_duration)
            return 0

        db = None
        extractor = None
        vault = None
        docs_keep = int((cfg.get('obsidian') or {}).get('docs_keep', 99))
        added = 0
        skipped = len(pre_skipped)
        errors = 0
        summaries: List[Dict[str, Any]] = []
        with _make_progress(total=len(files_to_process), display=args.display) as prog:
            prog.update(f"Pre-checking {len(files)} file(s)…", advance=0)
            prog.update("Connecting to DB…", advance=0)
            db, _ = _load_similarity_required()
            extractor = _build_extractor(cfg)
            vault = _load_vault()
            for f in files_to_process:
                prog.update(f"{f.name} • extract", advance=0)
                try:
                    extract_start = time.perf_counter()
                    extraction = extractor.extract(f, persist=True)
                    extract_time = time.perf_counter() - extract_start
                except Exception as exc:
                    errors += 1
                    prog.update(f.name, advance=1)
                    summaries.append({
                        "path": f,
                        "status": f"error: {exc}",
                        "hash": hash_times.get(f),
                        "extract": None,
                        "embed": None,
                        "db": None,
                        "chunks": None,
                        "obsidian": None,
                    })
                    continue

                prog.update(f"{f.name} • embed", advance=0)
                updated = False
                rec_timings: Dict[str, float] = {}
                kwargs: Dict[str, Any] = {}
                checksum_value = checksums.get(f)
                if checksum_value is not None:
                    kwargs['file_checksum'] = checksum_value
                size_value = file_sizes.get(f)
                if size_value is not None:
                    kwargs['file_bytes'] = size_value
                try:
                    updated = db.add_file(
                        f,
                        extraction=extraction,
                        **kwargs,
                    )
                    rec = db.get_last_add_result() or {}
                    rec_timings = rec.get('timings') or {}
                except Exception:
                    errors += 1
                    prog.update(f.name, advance=1)
                    summaries.append({
                        "path": f,
                        "status": "error",
                        "hash": hash_times.get(f),
                        "extract": extract_time,
                        "embed": None,
                        "db": None,
                        "chunks": None,
                        "obsidian": None,
                    })
                    continue

                obsidian_time: Optional[float] = None
                if updated:
                    added += 1
                    rec = db.get_last_add_result() or {}
                    ch = rec.get('content_checksum') or rec.get('content_hash')
                    txt = rec.get('text')
                    if ch and txt is not None:
                        try:
                            prog.update(f"{f.name} • obsidian", advance=0)
                            obs_start = time.perf_counter()
                            vault.write_doc_text(ch, f, txt, keep=docs_keep)
                            obsidian_time = time.perf_counter() - obs_start
                        except Exception:
                            obsidian_time = None
                else:
                    skipped += 1

                prog.update(f.name, advance=1)
                summaries.append({
                    "path": f,
                    "status": "updated" if updated else "unchanged",
                    "hash": hash_times.get(f),
                    "extract": extract_time,
                    "embed": rec_timings.get('embed'),
                    "db": rec_timings.get('db_update'),
                    "chunks": rec_timings.get('chunks'),
                    "obsidian": obsidian_time,
                })
            prog.update("DB update complete", advance=0)

        for f in pre_skipped:
            summaries.append({
                "path": f,
                "status": "cached",
                "hash": hash_times.get(f),
                "extract": None,
                "embed": None,
                "db": None,
                "chunks": None,
                "obsidian": None,
            })

        db_payload: Optional[Dict[str, Any]] = None
        try:
            stats = db.get_stats()
            if stats:
                db_payload = {
                    "database": stats.get("database"),
                    "collection": stats.get("collection"),
                    "total_files": stats.get("total_files"),
                    "total_bytes": stats.get("total_bytes"),
                }
        except Exception:
            stats = None
        payload = {
            "mode": "index",
            "requested": [str(p) for p in files],
            "added": added,
            "skipped": skipped,
            "errors": errors,
            "files": [
                {
                    "path": str(entry["path"]),
                    "status": entry["status"],
                    "timings": {
                        "hash": entry.get("hash"),
                        "extract": entry.get("extract"),
                        "embed": entry.get("embed"),
                        "db": entry.get("db"),
                        "chunks": entry.get("chunks"),
                        "obsidian": entry.get("obsidian"),
                    },
                }
                for entry in summaries
            ],
        }
        if db_payload:
            payload["database"] = db_payload
        _maybe_write_json(args, payload)

        print(f"Indexed {added} file(s), skipped {skipped}, errors {errors}")

        if summaries:
            _render_timing_summary(summaries, display_mode, _fmt_duration)
        if db_payload:
            total_bytes = db_payload.get("total_bytes")
            if total_bytes is not None:
                print(
                    f"DB: {db_payload['database']}.{db_payload['collection']} total_files={db_payload['total_files']} total_bytes={total_bytes}"
                )
            else:
                print(
                    f"DB: {db_payload['database']}.{db_payload['collection']} total_files={db_payload['total_files']}"
                )
        return 0
    idx.set_defaults(func=_index_cmd)

    # Related command: find semantically similar documents
    rel = sub.add_parser("related", help="Find semantically similar documents")
    rel.add_argument("path", help="Reference file to find similar documents for")
    rel.add_argument("--limit", type=int, default=10, help="Maximum number of results (default: 10)")
    rel.add_argument("--min-similarity", type=float, default=0.0, help="Minimum similarity threshold 0.0-1.0 (default: 0.0)")
    rel.add_argument("--format", choices=["table", "json"], default="table", help="Output format (default: table)")
    def _related_cmd(args: argparse.Namespace) -> int:
        """Find semantically similar documents."""
        from pathlib import Path

        display = args.display_obj

        # Parse input path
        query_path = Path(args.path).expanduser().resolve()
        if not query_path.exists():
            display.error(f"File not found: {query_path}")
            return 2

        # Load similarity DB
        display.status("Loading similarity database...")
        try:
            db, _ = _load_similarity_required()
            display.success("Connected to database")
        except SystemExit as e:
            return e.code if isinstance(e.code, int) else 1
        except Exception as e:
            display.error(f"Error loading similarity database: {e}")
            return 2

        # Find similar documents
        display.status(f"Finding similar documents to: {query_path.name}")
        try:
            results = db.find_similar(
                query_path=query_path,
                limit=args.limit,
                min_similarity=args.min_similarity,
                mode="file"
            )
        except Exception as e:
            display.error(f"Error finding similar documents: {e}")
            return 2
        finally:
            try:
                db.client.close()
            except Exception:
                pass

        # Format output
        if args.format == "json" or args.display == "mcp":
            # JSON output
            output = []
            for path_uri, similarity in results:
                # Convert file:// URI to path if needed
                if path_uri.startswith("file://"):
                    from urllib.parse import unquote, urlparse
                    parsed = urlparse(path_uri)
                    display_path = Path(unquote(parsed.path or ""))
                else:
                    display_path = Path(path_uri)

                output.append({
                    "path": str(display_path),
                    "similarity": round(similarity, 3)
                })
            display.json_output(output)
        else:
            # Table format
            if not results:
                display.info(f"No similar documents found for: {query_path}")
                return 0

            # Prepare table data
            table_data = []
            for path_uri, similarity in results:
                # Convert file:// URI to path if needed
                if path_uri.startswith("file://"):
                    from urllib.parse import unquote, urlparse
                    parsed = urlparse(path_uri)
                    display_path = Path(unquote(parsed.path or ""))
                else:
                    display_path = Path(path_uri)

                # Format similarity as percentage
                sim_pct = similarity * 100
                table_data.append({
                    "Similarity": f"{sim_pct:5.1f}%",
                    "Path": str(display_path)
                })

            display.table(table_data, title=f"Similar to: {query_path}")

        return 0
    rel.set_defaults(func=_related_cmd)

    # DB command: simple query passthrough and stats
    dbp = sub.add_parser("db", help="Database helpers: query and stats")
    dbsub = dbp.add_subparsers(dest="db_cmd")
    dbq = dbsub.add_parser("query", help="Run a JSON query against the selected DB space")
    # Choose logical DB space: --space (embeddings) or --time (snapshots)
    scope = dbq.add_mutually_exclusive_group(required=True)
    scope.add_argument("--space", action="store_true", help="Query the space DB (embeddings)")
    scope.add_argument("--time", action="store_true", help="Query the time DB (snapshots)")
    dbq.add_argument('--filter', default='{}', help='JSON filter, e.g. {"path": {"$regex": "2025-WKS"}}')
    dbq.add_argument('--projection', default=None, help='JSON projection, e.g. {"path":1,"timestamp":1}')
    dbq.add_argument("--limit", type=int, default=20)
    dbq.add_argument("--sort", default=None, help="Sort spec 'field:asc|desc' (optional)")
    def _db_query(args: argparse.Namespace) -> int:
        cfg_local = load_config()
        space_tag, time_tag = resolve_db_compatibility(cfg_local)
        pkg_version = get_package_version()
        try:
            client, mongo_cfg = _mongo_client_params(cfg=cfg_local)
        except Exception as e:
            print(f"DB connection failed: {e}")
            return 2
        try:
            import json as _json
            filt = _json.loads(args.filter or "{}")
            proj = _json.loads(args.projection) if args.projection else None
        except Exception as e:
            print(f"Invalid JSON: {e}")
            return 2
        # Decide target collection by logical DB
        if args.space:
            coll_name = mongo_cfg['space_collection']
            scope_label = 'space'
            try:
                ensure_db_compat(
                    client,
                    mongo_cfg['space_database'],
                    scope_label,
                    space_tag,
                    product_version=pkg_version,
                )
            except IncompatibleDatabase as exc:
                print(exc)
                return 2
            coll = client[mongo_cfg['space_database']][coll_name]
        else:
            coll_name = mongo_cfg['time_collection']
            scope_label = 'time'
            try:
                ensure_db_compat(
                    client,
                    mongo_cfg['time_database'],
                    scope_label,
                    time_tag,
                    product_version=pkg_version,
                )
            except IncompatibleDatabase as exc:
                print(exc)
                return 2
            coll = client[mongo_cfg['time_database']][coll_name]
        try:
            cur = coll.find(filt, proj)
        except Exception as e:
            print(f"DB query failed: {e}")
            return 1
        if args.sort:
            try:
                fld, dirspec = args.sort.split(':',1)
                direction = 1 if dirspec.lower().startswith('asc') else -1
                cur = cur.sort(fld, direction)
            except Exception:
                pass
        if args.limit:
            cur = cur.limit(int(args.limit))
        try:
            record_db_activity(f"db.query.{scope_label}", args.filter or "{}")
        except Exception:
            pass
        docs = list(cur)
        payload = {
            "scope": scope_label,
            "collection": coll_name,
            "count": len(docs),
            "documents": docs,
        }
        _maybe_write_json(args, payload)
        if not _display_enabled(args.display):
            return 0
        if args.display == "markdown":
            rows = [
                _json_dumps(doc) if not isinstance(doc, str) else doc
                for doc in docs
            ]
            print(
                render_template(
                    DB_QUERY_MARKDOWN_TEMPLATE,
                    {"scope": scope_label, "collection": coll_name, "rows": rows},
                )
            )
            return 0
        use_rich = args.display in {"rich", "plain"}
        if use_rich:
            try:
                from rich import box
                from rich.console import Console
                from rich.table import Table

                table_box = box.SQUARE if args.display == "rich" else box.SIMPLE
                header_style = "bold" if args.display == "rich" else ""
                table = Table(
                    title=f"[{scope_label}] {coll_name} query",
                    header_style=header_style,
                    box=table_box,
                    expand=False,
                    pad_edge=False,
                )
                table.add_column("#", justify="right", no_wrap=True)
                table.add_column("Document", overflow="fold")
                for idx, doc in enumerate(docs, 1):
                    table.add_row(str(idx), str(doc))
                Console().print(table)
                return 0
            except Exception:
                use_rich = False
        if not use_rich:
            for idx, doc in enumerate(docs, 1):
                print(f"[{idx}] {doc}")
        return 0
    dbq.set_defaults(func=_db_query)

    def _db_info(args: argparse.Namespace) -> int:
        # Use a lightweight, fast Mongo client for stats (no model/docling startup)
        cfg_local = load_config()
        ts_format = timestamp_format(cfg_local)
        display_mode = args.display

        reference_input = getattr(args, 'reference', None)
        reference_uri: Optional[str] = None
        reference_path: Optional[Path] = None
        reference_info: Optional[Dict[str, Any]] = None
        db_idx = None
        if reference_input:
            from urllib.parse import unquote, urlparse

            if reference_input.startswith("file://"):
                parsed = urlparse(reference_input)
                reference_uri = reference_input
                reference_path = Path(unquote(parsed.path or "")).expanduser()
            else:
                reference_path = Path(reference_input).expanduser()
                reference_uri = _as_file_uri_local(reference_path)
            if not reference_path.exists():
                print(f"Reference file not found: {reference_path}")
                return 2
            try:
                db_idx, _ = _load_similarity_required()
                extractor = _build_extractor(cfg_local)
                checksum_val = None
                size_val = None
                try:
                    checksum_val = _file_checksum(reference_path)
                except Exception:
                    checksum_val = None
                try:
                    size_val = reference_path.stat().st_size
                except Exception:
                    size_val = None
                extraction = extractor.extract(reference_path, persist=True)
                db_idx.add_file(
                    reference_path,
                    extraction=extraction,
                    file_checksum=checksum_val,
                    file_bytes=size_val,
                )
            except SystemExit:
                raise
            except Exception as exc:
                print(f"Failed to index reference: {exc}")
                return 2
            finally:
                if db_idx is not None:
                    try:
                        db_idx.client.close()
                    except Exception:
                        pass
            reference_info = {"uri": reference_uri, "path": reference_path}
        else:
            reference_info = None

        try:
            client, mongo_cfg = _mongo_client_params(server_timeout=300, connect_timeout=300, cfg=cfg_local)
        except Exception as e:
            try:
                mongoctl.ensure_mongo_running(_default_mongo_uri(), record_start=True)
                client, mongo_cfg = _mongo_client_params(server_timeout=300, connect_timeout=300, cfg=cfg_local)
            except Exception:
                print(f"DB connection failed: {e}")
                return 2
        try:
            client.admin.command('ping')
        except Exception as e:
            print(f"DB unreachable: {e}")
            return 1
        space_tag, time_tag = resolve_db_compatibility(cfg_local)
        pkg_version = get_package_version()
        info_scope = "time" if getattr(args, "time", False) else "space"
        target_db = mongo_cfg['time_database'] if info_scope == "time" else mongo_cfg['space_database']
        compat_tag = time_tag if info_scope == "time" else space_tag
        try:
            ensure_db_compat(
                client,
                target_db,
                info_scope,
                compat_tag,
                product_version=pkg_version,
            )
        except IncompatibleDatabase as exc:
            print(exc)
            return 2
        coll_space = mongo_cfg['space_collection']
        coll_time = mongo_cfg['time_collection']
        if reference_info and getattr(args, 'time', False):
            print("Reference comparisons are only available for the space database.")
            return 2
        # Helper to format timestamps consistently
        from datetime import datetime as _dt
        def _fmt_ts(ts):
            if not ts:
                return ""
            try:
                if isinstance(ts, str):
                    s = ts.replace('Z','+00:00') if ts.endswith('Z') else ts
                    dt = _dt.fromisoformat(s)
                else:
                    dt = _dt.fromtimestamp(float(ts))
                return dt.strftime(ts_format)
            except Exception:
                return str(ts)

        def _fmt_bytes(value: Optional[Any]) -> str:
            try:
                if value is None:
                    return "-"
                bytes_val = float(value)
            except Exception:
                return "-"
            units = ['B', 'kB', 'MB', 'GB', 'TB']
            i = 0
            while bytes_val >= 1024.0 and i < len(units) - 1:
                bytes_val /= 1024.0
                i += 1
            return f"{bytes_val:7.2f} {units[i]:>2}"

        def _fmt_uri(doc: Dict[str, Any]) -> str:
            uri = doc.get('path')
            if uri:
                return str(uri)
            local = doc.get('path_local')
            if not local:
                return ""
            try:
                return Path(local).expanduser().resolve().as_uri()
            except Exception:
                return str(local)

        def _fmt_checksum(value: Optional[Any]) -> str:
            if value is None or value == "":
                return "-"
            text = str(value)
            if len(text) <= 10:
                return text
            return f"{text[:10]} …"

        def _parse_ts_value(ts: Any) -> Optional[_dt]:
            if not ts:
                return None
            try:
                if isinstance(ts, str):
                    s = ts.replace("Z", "+00:00") if ts.endswith("Z") else ts
                    return _dt.fromisoformat(s)
                if isinstance(ts, (int, float)):
                    return _dt.fromtimestamp(float(ts))
            except Exception:
                return None
            return None

        def _fmt_tdelta(delta: Optional[Any]) -> str:
            if delta is None:
                return "-"
            if not isinstance(delta, (int, float)):
                total_seconds = int(delta.total_seconds())
            else:
                total_seconds = int(delta)
            sign = "+" if total_seconds >= 0 else "-"
            total_seconds = abs(total_seconds)
            days, rem = divmod(total_seconds, 86400)
            hours, rem = divmod(rem, 3600)
            minutes, seconds = divmod(rem, 60)
            if days:
                return f"{sign}{days}d {hours:02d}:{minutes:02d}:{seconds:02d}"
            return f"{sign}{hours:02d}:{minutes:02d}:{seconds:02d}"

        def _fmt_size_delta(delta: Optional[Any]) -> str:
            if delta is None:
                return "-"
            try:
                value = float(delta)
            except Exception:
                return "-"
            sign = "+" if value >= 0 else "-"
            value = abs(value)
            units = ['B', 'kB', 'MB', 'GB', 'TB']
            i = 0
            while value >= 1024.0 and i < len(units) - 1:
                value /= 1024.0
                i += 1
            return f"{sign}{value:7.2f} {units[i]:>2}"

        def _fmt_angle_delta(delta: Optional[float]) -> str:
            if delta is None:
                return "-"
            return f"{delta:6.2f}°"

        def _angle_between(vec_a: Optional[List[Any]], vec_b: Optional[List[Any]]) -> Optional[float]:
            if not vec_a or not vec_b:
                return None
            try:
                pairs = list(zip(vec_a, vec_b))
                if not pairs:
                    return None
                dot = sum(float(a) * float(b) for a, b in pairs)
                norm_a = math.sqrt(sum(float(a) * float(a) for a in vec_a))
                norm_b = math.sqrt(sum(float(b) * float(b) for b in vec_b))
                denom = norm_a * norm_b
                if denom <= 0:
                    return None
                cosv = max(-1.0, min(1.0, dot / denom))
                return math.degrees(math.acos(cosv))
            except Exception:
                return None

        def _format_cell(text: str, width: int, align: str) -> str:
            if align == "right":
                return text.rjust(width)
            if align == "center":
                return text.center(width)
            return text.ljust(width)

        def _render_plain_boxed_table_simple(
            title: str,
            header: List[str],
            rows: List[List[str]],
            align: List[str],
            limits: Optional[Dict[int, int]] = None,
        ) -> None:
            if not rows:
                return
            limits = limits or {}
            processed: List[List[str]] = []
            for row in rows:
                processed_row: List[str] = []
                for idx, cell in enumerate(row):
                    text = str(cell)
                    limit = limits.get(idx)
                    if limit and len(text) > limit:
                        if limit == 1:
                            text = text[:1]
                        else:
                            text = text[: limit - 1] + "…"
                    processed_row.append(text)
                processed.append(processed_row)
            widths: List[int] = []
            for idx, head in enumerate(header):
                col_width = len(str(head))
                for row in processed:
                    col_width = max(col_width, len(row[idx]))
                limit = limits.get(idx)
                if limit:
                    col_width = min(col_width, limit)
                widths.append(col_width)
            total_width = sum(widths) + 3 * (len(widths) - 1)
            border = "+" + "-" * (total_width + 2) + "+"
            print()
            print(border)
            print("| " + title.center(total_width) + " |")
            print(border)
            header_line = " | ".join(
                _format_cell(str(head), widths[idx], "center" if align[idx] == "right" else align[idx])
                for idx, head in enumerate(header)
            )
            print("| " + header_line + " |")
            separator = "-+-".join("-" * width for width in widths)
            print("| " + separator + " |")
            for row in processed:
                line = " | ".join(
                    _format_cell(cell, widths[idx], align[idx]) for idx, cell in enumerate(row)
                )
                print("| " + line + " |")
            print(border)

        if args.time:
            coll = client[mongo_cfg['time_database']][coll_time]
            total = coll.count_documents({})
            if display_mode != 'json':
                print({"database": mongo_cfg['time_database'], "collection": coll_time, "total_docs": total})
            try:
                record_db_activity("db.info.time", f"total={total}")
            except Exception:
                pass
            n = int(getattr(args, 'latest', 0) or 0)
            if n > 0:
                cur = coll.find(
                    {},
                    {"path": 1, "t_new": 1, "checksum_new": 1, "size_bytes_new": 1, "bytes_delta": 1},
                ).sort("t_new_epoch", -1).limit(n)
                docs = list(cur)
                if display_mode == 'json':
                    latest_payload = []
                    for doc in docs:
                        latest_payload.append({
                            "timestamp": _fmt_ts(doc.get('t_new', '')),
                            "uri": _fmt_uri(doc),
                            "checksum": _fmt_checksum(doc.get('checksum_new') or doc.get('content_hash')),
                            "size_bytes": doc.get('size_bytes_new'),
                            "bytes_delta": doc.get('bytes_delta'),
                        })
                    payload = {
                        "database": mongo_cfg['time_database'],
                        "collection": coll_time,
                        "total_docs": total,
                        "latest": latest_payload,
                    }
                    print(json.dumps(payload, indent=2))
                    return 0
                use_rich = (display_mode == 'rich') or (display_mode == 'auto')
                try:
                    from rich.console import Console
                    from rich.table import Table
                    if use_rich:
                        t = Table(title=f"[time] latest {n} snapshots")
                        t.add_column("#", justify="right", no_wrap=True, overflow="ignore")
                        t.add_column("t_new", no_wrap=True, overflow="ignore", min_width=19)
                        t.add_column("path", overflow="fold")
                        t.add_column("checksum", no_wrap=True, overflow="ignore", min_width=14)
                        t.add_column("bytes", justify="right", no_wrap=True, overflow="ignore", min_width=10)
                        t.add_column("Δ bytes", justify="right", no_wrap=True, overflow="ignore", min_width=10)
                        for i, doc in enumerate(docs, 1):
                            checksum = _fmt_checksum(doc.get('checksum_new') or doc.get('content_hash'))
                            size_disp = _fmt_bytes(doc.get('size_bytes_new'))
                            delta = doc.get('bytes_delta')
                            delta_disp = f"{delta:+}" if isinstance(delta, (int, float)) else "-"
                            t.add_row(
                                str(i),
                                _fmt_ts(doc.get('t_new', '')),
                                _fmt_uri(doc),
                                checksum,
                                size_disp,
                                delta_disp,
                            )
                        Console().print(t)
                    else:
                        for i, doc in enumerate(docs, 1):
                            checksum = _fmt_checksum(doc.get('checksum_new') or doc.get('content_hash'))
                            size_disp = _fmt_bytes(doc.get('size_bytes_new'))
                            delta = doc.get('bytes_delta')
                            delta_disp = f"{delta:+}" if isinstance(delta, (int, float)) else "-"
                            print(
                                f"[{i}] {_fmt_ts(doc.get('t_new',''))} checksum={checksum} size={size_disp} delta={delta_disp} {_fmt_uri(doc)}"
                            )
                except Exception:
                    for i, doc in enumerate(docs, 1):
                        checksum = _fmt_checksum(doc.get('checksum_new') or doc.get('content_hash'))
                        size_disp = _fmt_bytes(doc.get('size_bytes_new'))
                        delta = doc.get('bytes_delta')
                        delta_disp = f"{delta:+}" if isinstance(delta, (int, float)) else "-"
                        print(
                            f"[{i}] {_fmt_ts(doc.get('t_new',''))} checksum={checksum} size={size_disp} delta={delta_disp} {_fmt_uri(doc)}"
                        )
            elif display_mode == 'json':
                payload = {
                    "database": mongo_cfg['time_database'],
                    "collection": coll_time,
                    "total_docs": total,
                    "latest": [],
                }
                print(json.dumps(payload, indent=2))
                return 0
            return 0
        else:
            coll = client[mongo_cfg['space_database']][coll_space]
            total = coll.count_documents({})
            if display_mode != 'json':
                print(f"tracked files: {total}")
            try:
                record_db_activity("db.info.space", f"total={total}")
            except Exception:
                pass
            if reference_info:
                uri = reference_info.get("uri")
                ref_path_obj = reference_info.get("path")
                ref_doc = None
                if uri:
                    ref_doc = coll.find_one({"path": uri})
                if ref_doc is None and ref_path_obj is not None:
                    ref_doc = coll.find_one({"path_local": str(ref_path_obj.resolve())})
                if not ref_doc:
                    print("Reference document not found in the database.")
                    return 2
                ref_embedding = ref_doc.get("embedding")
                if not ref_embedding:
                    print("Reference document is missing embedding data; re-index and retry.")
                    return 2
                ref_ts = _parse_ts_value(ref_doc.get("timestamp"))
                ref_bytes = ref_doc.get("bytes")
                ref_checksum = ref_doc.get("checksum")

                entries: List[Dict[str, Any]] = []
                cursor = coll.find({}, {"path": 1, "path_local": 1, "timestamp": 1, "checksum": 1, "bytes": 1, "embedding": 1})
                for doc in cursor:
                    emb = doc.get("embedding")
                    angle_delta = _angle_between(ref_embedding, emb)
                    if angle_delta is None:
                        continue
                    other_ts = _parse_ts_value(doc.get("timestamp"))
                    t_delta = None
                    if other_ts is not None and ref_ts is not None:
                        t_delta = (other_ts - ref_ts).total_seconds()
                    size_delta = None
                    bytes_val = doc.get("bytes")
                    if bytes_val is not None and ref_bytes is not None:
                        try:
                            size_delta = int(bytes_val) - int(ref_bytes)
                        except Exception:
                            size_delta = None
                    checksum_same = False
                    if ref_checksum is not None:
                        checksum_same = doc.get("checksum") == ref_checksum
                    entries.append({
                        "doc": doc,
                        "angle_delta": angle_delta,
                        "time_delta": t_delta,
                        "size_delta": size_delta,
                        "checksum_same": checksum_same,
                    })

                entries.sort(key=lambda e: (abs(e['angle_delta']) if e['angle_delta'] is not None else float('inf'), e['doc'].get('path', '')))
                limit_n = int(getattr(args, 'latest', 0) or 10)
                if limit_n > 0:
                    entries = entries[:limit_n]

                try:
                    record_db_activity("db.info.reference", title_label)
                except Exception:
                    pass

                use_rich = False
                try:
                    if display_mode == 'rich':
                        use_rich = True
                    elif display_mode in (None, 'auto'):
                        use_rich = sys.stdout.isatty()
                except Exception:
                    use_rich = False

                title_label = uri or (str(ref_path_obj.resolve()) if ref_path_obj is not None else "reference")
                if display_mode == 'json':
                    json_entries: List[Dict[str, Any]] = []
                    for entry in entries:
                        doc = entry['doc']
                        json_entries.append({
                            "uri": _fmt_uri(doc),
                            "timestamp": _fmt_ts(doc.get('timestamp', '')),
                            "angle_delta": entry['angle_delta'],
                            "checksum_same": bool(entry['checksum_same']),
                            "size_delta": entry['size_delta'],
                            "time_delta_secs": entry['time_delta'],
                        })
                    payload = {
                        "reference": title_label,
                        "tracked_files": total,
                        "entries": json_entries,
                    }
                    print(json.dumps(payload, indent=2))
                    return 0
                if use_rich:
                    try:
                        from rich import box
                        from rich.console import Console
                        from rich.panel import Panel
                        from rich.table import Table
                    except Exception:
                        use_rich = False
                if use_rich:
                    console = Console()
                    table = Table(show_header=True, header_style="bold", box=box.SQUARE, expand=False, pad_edge=False)
                    table.add_column("#", justify="right", width=3, no_wrap=True)
                    table.add_column("Δ time", justify="right", no_wrap=True)
                    table.add_column("Checksum", justify="left", no_wrap=True)
                    table.add_column("Δ size", justify="right", no_wrap=True)
                    table.add_column("Δ angle", justify="right", no_wrap=True)
                    table.add_column("uri", overflow="fold")
                    for idx, entry in enumerate(entries, 1):
                        checksum_label = "same" if entry['checksum_same'] else "diff"
                        checksum_display = f"[green]{checksum_label}[/]" if entry['checksum_same'] else f"[red]{checksum_label}[/]"
                        table.add_row(
                            str(idx),
                            _fmt_tdelta(entry['time_delta']) if entry['time_delta'] is not None else "-",
                            checksum_display,
                            _fmt_size_delta(entry['size_delta']),
                            _fmt_angle_delta(entry['angle_delta']),
                            _fmt_uri(entry['doc'])
                        )
                    console.print(Panel.fit(table, title=f"Reference: {title_label}", border_style="dim"))
                    return 0

                header = ["#", "Δ time", "Checksum", "Δ size", "Δ angle", "uri"]
                align_plain = ["right", "right", "left", "right", "right", "left"]
                limits_plain = {5: 80}
                rows_plain: List[List[str]] = []
                for idx, entry in enumerate(entries, 1):
                    rows_plain.append([
                        str(idx),
                        _fmt_tdelta(entry['time_delta']) if entry['time_delta'] is not None else "-",
                        "same" if entry['checksum_same'] else "diff",
                        _fmt_size_delta(entry['size_delta']),
                        _fmt_angle_delta(entry['angle_delta']),
                        _fmt_uri(entry['doc']),
                    ])
                _render_plain_boxed_table_simple(f"Reference: {title_label}", header, rows_plain, align_plain, limits_plain)
                return 0

            n = int(getattr(args, 'latest', 0) or 0)
            if n > 0:
                cur = coll.find({}, {"path": 1, "path_local": 1, "timestamp": 1, "checksum": 1, "bytes": 1, "angle": 1}).sort("timestamp", -1).limit(n)
                docs = list(cur)
                latest_docs_payload = [
                    {
                        "timestamp": _fmt_ts(doc.get('timestamp', '')),
                        "checksum": _fmt_checksum(doc.get('checksum') or doc.get('content_hash')),
                        "bytes": doc.get('bytes'),
                        "angle": doc.get('angle'),
                        "uri": _fmt_uri(doc),
                    }
                    for doc in docs
                ]
                if display_mode == 'json':
                    payload = {
                        "tracked_files": total,
                        "latest": latest_docs_payload,
                    }
                    print(json.dumps(payload, indent=2))
                    return 0
                use_rich = (display_mode == 'rich') or (display_mode == 'auto')
                try:
                    from rich.console import Console
                    from rich.table import Table
                    if use_rich:
                        t = Table(title=f"[space] latest {n} files")
                        t.add_column("#", justify="right", no_wrap=True, overflow="ignore")
                        t.add_column("timestamp", no_wrap=True, overflow="ignore", min_width=19)
                        t.add_column("checksum", no_wrap=True, overflow="ignore", min_width=14)
                        t.add_column("size", justify="right", no_wrap=True, overflow="ignore", min_width=10)
                        t.add_column("angle", justify="right", no_wrap=True, overflow="ignore", min_width=8)
                        t.add_column("uri", overflow="fold")
                        for i, doc in enumerate(docs, 1):
                            checksum = _fmt_checksum(doc.get('checksum') or doc.get('content_hash'))
                            size_disp = _fmt_bytes(doc.get('bytes'))
                            angle = doc.get('angle')
                            angle_disp = f"{float(angle):6.2f}°" if isinstance(angle, (int, float)) else "-"
                            t.add_row(
                                str(i),
                                _fmt_ts(doc.get('timestamp','')),
                                checksum,
                                size_disp,
                                angle_disp,
                                _fmt_uri(doc),
                            )
                        Console().print(t)
                    else:
                        for i, doc in enumerate(docs, 1):
                            checksum = _fmt_checksum(doc.get('checksum') or doc.get('content_hash'))
                            size_disp = _fmt_bytes(doc.get('bytes'))
                            angle = doc.get('angle')
                            angle_disp = f"{float(angle):6.2f}°" if isinstance(angle, (int, float)) else "-"
                            print(
                                f"[{i}] {_fmt_ts(doc.get('timestamp',''))} checksum={checksum} size={size_disp} angle={angle_disp} {_fmt_uri(doc)}"
                            )
                except Exception:
                    for i, doc in enumerate(docs, 1):
                        checksum = _fmt_checksum(doc.get('checksum') or doc.get('content_hash'))
                        size_disp = _fmt_bytes(doc.get('bytes'))
                        angle = doc.get('angle')
                        angle_disp = f"{float(angle):6.2f}°" if isinstance(angle, (int, float)) else "-"
                        print(
                            f"[{i}] {_fmt_ts(doc.get('timestamp',''))} checksum={checksum} size={size_disp} angle={angle_disp} {_fmt_uri(doc)}"
                        )
            elif display_mode == 'json':
                payload = {
                    "tracked_files": total,
                    "latest": [],
                }
                print(json.dumps(payload, indent=2))
                return 0
            return 0

    dbinfo = dbsub.add_parser("info", help="Print tracked file count and latest files")
    scope_info = dbinfo.add_mutually_exclusive_group()
    scope_info.add_argument("--space", action="store_true", help="Stats for the space DB")
    scope_info.add_argument("--time", action="store_true", help="Stats for the time DB")
    dbinfo.add_argument("-n", "--latest", type=int, default=10, help="Show the most recent N records (default 10)")
    dbinfo.add_argument("--reference", help="File path or file:// URI to compare against")
    dbinfo.set_defaults(func=_db_info)
    # DB reset: drop Mongo database and remove local mongod files (if any)
    dbr = dbsub.add_parser("reset", help="Drop WKS Mongo databases and local DB files (space/time)")
    def _db_reset(args: argparse.Namespace) -> int:
        cfg = load_config()
        mongo_cfg = mongo_settings(cfg)
        uri = mongo_cfg['uri']
        space_db = mongo_cfg['space_database']
        time_db = mongo_cfg['time_database']
        _stop_managed_mongo()
        # Try to drop DB via pymongo
        try:
            client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=3000)
            try:
                client.admin.command('ping')
                dropped = set()
                client.drop_database(space_db)
                dropped.add(space_db)
                if time_db not in dropped:
                    client.drop_database(time_db)
                    dropped.add(time_db)
                print(f"Dropped database(s): {', '.join(sorted(dropped))}")
                try:
                    record_db_activity("db.reset", ",".join(sorted(dropped)))
                except Exception:
                    pass
            except Exception as e:
                print(f"DB drop skipped (unreachable or error): {e}")
        except Exception as e:
            print(f"Mongo client unavailable: {e}")
        # Stop local mongod on 27027 (best-effort)
        try:
            import shutil as _sh, subprocess as _sp
            if _sh.which('pkill'):
                _sp.run(['pkill','-f','mongod.*27027'], check=False)
        except Exception:
            pass
        # Remove local DB files
        try:
            import shutil as _sh
            dbroot = Path.home()/WKS_HOME_EXT/'mongodb'
            if dbroot.exists():
                _sh.rmtree(dbroot, ignore_errors=True)
                print(f"Removed local DB files: {dbroot}")
        except Exception:
            pass
        # Ensure Mongo comes back up so the service can reconnect immediately
        try:
            mongoctl.ensure_mongo_running(uri, record_start=True)
        except SystemExit:
            raise
        except Exception:
            pass
        return 0
    dbr.set_defaults(func=_db_reset)

    # Simplified CLI — top-level groups: config/service/monitor/extract/index/related/db

    args = parser.parse_args(argv)

    # Get display instance based on mode
    args.display_obj = get_display(args.display)

    if not hasattr(args, "func"):
        # If a group was selected without subcommand, show that group's help
        try:
            cmd = getattr(args, 'cmd', None)
            if cmd == 'service':
                svc.print_help()
                return 2
            if cmd == 'monitor':
                mon.print_help()
                return 2
            if cmd == 'db':
                dbp.print_help()
                return 2
        except Exception:
            pass
        parser.print_help()
        return 2

    res = args.func(args)
    return 0 if res is None else res


if __name__ == "__main__":
    raise SystemExit(main())
