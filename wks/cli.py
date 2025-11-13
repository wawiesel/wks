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

from .monitor_controller import MonitorController, MonitorValidator
from .config import (
    apply_similarity_mongo_defaults,
    mongo_settings,
    DEFAULT_TIMESTAMP_FORMAT,
    timestamp_format,
    load_config as config_load_config,
    get_config_path,
)
from .constants import WKS_HOME_EXT, WKS_EXTRACT_EXT, WKS_DOT_DIRS, WKS_HOME_DISPLAY
from .display.context import get_display, add_display_argument
from .extractor import Extractor
from .status import record_db_activity, load_db_activity_summary, load_db_activity_history
from .service_controller import (
    LOCK_FILE,
    ServiceController,
    ServiceStatusData,
    ServiceStatusLaunch,
    agent_installed,
    daemon_start_launchd,
    daemon_status_launchd,
    daemon_stop_launchd,
    default_mongo_uri,
    is_macos,
    stop_managed_mongo,
)
from .dbmeta import (
    IncompatibleDatabase,
    ensure_db_compat,
    resolve_db_compatibility,
)
from .utils import get_package_version
from . import mongoctl
from .templating import render_template
from . import cli_db


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


def _is_macos() -> bool:
    """Backward-compatible wrapper for legacy imports."""
    return is_macos()


def _agent_installed() -> bool:
    return agent_installed()


def _daemon_start_launchd():
    return daemon_start_launchd()


def _daemon_stop_launchd():
    return daemon_stop_launchd()


def _daemon_status_launchd() -> int:
    return daemon_status_launchd()


def _stop_managed_mongo() -> None:
    stop_managed_mongo()

def load_config() -> Dict[str, Any]:
    """Load WKS configuration from default location."""
    return config_load_config()


def _merge_defaults(defaults: List[str], user: Optional[List[str]]) -> List[str]:
    merged: List[str] = []
    for item in defaults:
        if item not in merged:
            merged.append(item)
    for item in user or []:
        if item not in merged:
            merged.append(item)
    return merged


def show_config(args: argparse.Namespace) -> int:
    """Show config file - table in CLI mode, JSON in MCP mode."""
    from .config import get_config_path
    import json as _json
    
    config_path = get_config_path()
    display = getattr(args, "display_obj", None) or get_display(getattr(args, "display", None))
    display_mode = getattr(args, "display", None)
    
    # Load raw config file
    try:
        with open(config_path, "r") as f:
            config_data = _json.load(f)
    except Exception as e:
        display.error(f"Failed to read config file: {config_path}", details=str(e))
        return 2
    
    # MCP mode: output raw JSON
    if display_mode == "mcp":
        display.json_output(config_data)
        return 0
    
    # CLI mode: show as table with sections
    table_data = []
    
    def _format_value(value: Any) -> str:
        """Format a config value for display."""
        if isinstance(value, list):
            if value and isinstance(value[0], str):
                return ", ".join(value)
            return str(value)
        elif isinstance(value, dict):
            return str(value)
        elif isinstance(value, bool):
            return "true" if value else "false"
        else:
            return str(value)
    
    def _add_section_items(section_name: str, section_data: Dict[str, Any]) -> None:
        """Add items from a config section."""
        for key, value in sorted(section_data.items()):
            if isinstance(value, dict):
                # Nested dict - add as subsection
                table_data.append({"Key": f"  {key}", "Value": ""})
                for subkey, subvalue in sorted(value.items()):
                    if isinstance(subvalue, dict):
                        # Deeply nested - show as string
                        table_data.append({"Key": f"    {subkey}", "Value": _format_value(subvalue)})
                    else:
                        table_data.append({"Key": f"    {subkey}", "Value": _format_value(subvalue)})
            else:
                table_data.append({"Key": f"  {key}", "Value": _format_value(value)})
    
    # Define section order and names (matching SPEC.md architecture)
    sections = [
        ("Monitor", "monitor"),
        ("Vault", "vault"),
        ("DB", "db"),
        ("Extract", "extract"),
        ("Diff", "diff"),
        ("Related", "related"),
        ("Index", "index"),
        ("Search", "search"),
        ("Display", "display"),
    ]
    
    for section_name, section_key in sections:
        if section_key in config_data:
            # Add section header
            table_data.append({"Key": section_name, "Value": ""})
            _add_section_items(section_name, config_data[section_key])
    
    # Add any remaining top-level keys not in our section list
    known_keys = {key for _, key in sections}
    remaining = {k: v for k, v in config_data.items() if k not in known_keys}
    if remaining:
        table_data.append({"Key": "Other", "Value": ""})
        for key, value in sorted(remaining.items()):
            table_data.append({"Key": f"  {key}", "Value": _format_value(value)})
    
    # Format table data with section header styling
    formatted_data = []
    for row in table_data:
        key = row["Key"]
        value = row["Value"]
        # Style section headers (empty value and not indented)
        if value == "" and not key.startswith("  "):
            formatted_data.append({"Key": f"[bold yellow]{key}[/bold yellow]", "Value": value})
        else:
            formatted_data.append({"Key": key, "Value": value})
    
    display.table(
        formatted_data,
        title=f"WKS Configuration ({config_path})",
        column_justify={"Key": "left", "Value": "left"},
        show_header=False
    )
    
    return 0


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
    live = getattr(args, "live", False)
    
    # Live mode only works with CLI display
    if live:
        display_mode = getattr(args, "display", None)
        if display_mode == "mcp":
            sys.stderr.write("--live mode is not supported with MCP display\n")
            return 2
        # Force CLI mode for live updates
        args.display = "cli"
        args.display_obj = get_display("cli")
    
    status = None
    try:
        status = ServiceController.get_status()
    except Exception as exc:
        display = getattr(args, "display_obj", None)
        if display:
            display.error("Failed to gather service status", details=str(exc))
        else:
            sys.stderr.write(f"Failed to gather service status: {exc}\n")
        return 2

    if status is None:
        return 2

    payload = status.to_dict()
    _maybe_write_json(args, payload)

    display_mode = getattr(args, "display", None)

    # Live mode: live updating display
    if live:
        try:
            from rich.console import Console
            from rich.live import Live
            from rich.table import Table
            from rich import box
        except ImportError:
            sys.stderr.write("Rich library required for --live mode. Install with: pip install rich\n")
            return 2
        
        console = Console()
        
        def _render_status() -> Table:
            """Render current status as a Rich table with grouped sections."""
            status = ServiceController.get_status()
            rows = status.to_rows()
            
            table = Table(
                title="WKS Service Status (Live)",
                header_style="bold cyan",
                box=box.SQUARE,
                expand=False,
                pad_edge=False,
                show_header=False,
            )
            table.add_column("", style="cyan", overflow="fold")
            table.add_column("", style="white", overflow="fold")
            
            for key, value in rows:
                # Style section headers
                if value == "" and not key.startswith("  "):
                    table.add_row(key, value, style="bold yellow")
                else:
                    table.add_row(key, value)
            
            return table
        
        try:
            with Live(_render_status(), refresh_per_second=0.5, screen=False, console=console) as live:
                while True:
                    time.sleep(2.0)  # Update every 2 seconds
                    try:
                        live.update(_render_status())
                    except Exception as update_exc:
                        # Continue on update errors, but show them
                        console.print(f"[yellow]Warning: {update_exc}[/yellow]", end="")
        except KeyboardInterrupt:
            console.print("\n[dim]Stopped monitoring.[/dim]")
            return 0
        except Exception as exc:
            console.print(f"[red]Error in live mode: {exc}[/red]")
            return 2

    # New display modes (CLI/MCP auto-detected)
    if display_mode in DISPLAY_CHOICES:
        display = args.display_obj
        if display_mode == "mcp":
            display.success("WKS service status", data=payload)
            return 0

        rows = status.to_rows()
        table_data = []
        for key, value in rows:
            # Style section headers in regular display too
            if value == "" and not key.startswith("  "):
                table_data.append({"Key": f"[bold yellow]{key}[/bold yellow]", "Value": value})
            else:
                table_data.append({"Key": key, "Value": value})
        display.table(table_data, title="WKS Service Status", column_justify={"Value": "left"})
        if status.notes:
            display.info("; ".join(status.notes))
        return 0

    # Legacy display behaviour
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

    # Fallback to JSON for unknown legacy modes
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

    # Config command - show config file
    cfg = sub.add_parser("config", help="Show configuration file")
    cfg.set_defaults(func=show_config)

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
    svcstatus2.add_argument(
        "--live",
        action="store_true",
        help="Keep display updated automatically (refreshes every 2 seconds)"
    )
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
        from .utils import wks_home_path
        config_file = get_config_path()
        display.info(f"Reading config from: {config_file}")

        wks_home_display = os.environ.get("WKS_HOME", str(wks_home_path()))
        display.info(f"WKS_HOME: {wks_home_display}")

        cfg = load_config()

        # Use MonitorController to get status (includes validation)
        status_data = MonitorController.get_status(cfg)

        # Extract data
        total_files = status_data["tracked_files"]
        issues = status_data["issues"]
        redundancies = status_data["redundancies"]
        managed_dirs_dict = status_data["managed_directories"]
        include_paths = set(status_data["include_paths"])
        exclude_paths = set(status_data["exclude_paths"])

        # Build table data
        table_data = [
            {"Setting": "Tracked Files", "Value": str(total_files)},
            {"Setting": "", "Value": ""},
            {"Setting": "managed_directories", "Value": str(len(managed_dirs_dict))},
        ]

        # Build sets of problematic paths for coloring
        red_paths = set()
        yellow_paths = set()
        for issue in issues:
            for path in list(managed_dirs_dict.keys()) + list(include_paths) + list(exclude_paths):
                if f"'{path}'" in issue or f" {path}" in issue or issue.endswith(path):
                    red_paths.add(path)

        for redund in redundancies:
            for path in list(managed_dirs_dict.keys()) + list(include_paths) + list(exclude_paths):
                if f"'{path}'" in redund or f" {path}" in redund or redund.endswith(path):
                    yellow_paths.add(path)

        # Calculate max pip count and max number width for alignment
        import math
        max_pip_count = 0
        max_num_width = 0
        for path_info in managed_dirs_dict.values():
            priority = path_info["priority"]
            if priority <= 1:
                pip_count = 1
            else:
                pip_count = int(math.log10(priority)) + 1
            max_pip_count = max(max_pip_count, pip_count)
            max_num_width = max(max_num_width, len(str(priority)))

        # Add managed directories with logarithmic pip visualization
        for path, path_info in sorted(managed_dirs_dict.items(), key=lambda x: -x[1]["priority"]):
            priority = path_info["priority"]
            is_valid = path_info["valid"]
            error_msg = path_info["error"]

            # Create logarithmic pip visualization
            if priority <= 1:
                pip_count = 1
            else:
                pip_count = int(math.log10(priority)) + 1
            pips = "▪" * pip_count

            # Get status symbol
            status_symbol = MonitorValidator.status_symbol(error_msg, is_valid)

            # Left-align pips, right-align numbers, add status symbol
            pips_padded = pips.ljust(max_pip_count)
            num_padded = str(priority).rjust(max_num_width)
            priority_display = f"{pips_padded} {num_padded} {status_symbol}"

            table_data.append({
                "Setting": f"  {path}",
                "Value": priority_display
            })

        table_data.append({"Setting": "", "Value": ""})
        table_data.append({"Setting": "include_paths", "Value": str(len(include_paths))})
        for path in sorted(include_paths):
            error_msg = None if path not in (red_paths | yellow_paths) else "issue"
            is_valid = path not in red_paths
            table_data.append({"Setting": f"  {path}", "Value": MonitorValidator.status_symbol(error_msg, is_valid)})

        table_data.append({"Setting": "", "Value": ""})
        table_data.append({"Setting": "exclude_paths", "Value": str(len(exclude_paths))})
        for path in sorted(exclude_paths):
            error_msg = None if path not in (red_paths | yellow_paths) else "issue"
            is_valid = path not in red_paths
            table_data.append({"Setting": f"  {path}", "Value": MonitorValidator.status_symbol(error_msg, is_valid)})

        # Get ignore rules from status data
        ignore_dirnames = status_data["ignore_dirnames"]
        ignore_globs = status_data["ignore_globs"]

        # Build ignore rules list with validation
        ignore_list = []
        ignore_list.append(("ignore_dirnames", str(len(ignore_dirnames))))
        ignore_list.append(("", ""))

        # Validate each ignore_dirname
        for dirname in ignore_dirnames:
            validation_info = status_data["ignore_dirname_validation"].get(dirname, {})
            error_msg = validation_info.get("error")
            is_valid = validation_info.get("valid", True)
            ignore_list.append((f"  {dirname}", MonitorValidator.status_symbol(error_msg, is_valid)))

        ignore_list.append(("", ""))
        ignore_list.append(("ignore_globs", str(len(ignore_globs))))

        # Validate each ignore_glob for syntax errors
        for glob_pattern in ignore_globs:
            validation_info = status_data["ignore_glob_validation"].get(glob_pattern, {})
            error_msg = validation_info.get("error")
            is_valid = validation_info.get("valid", True)
            ignore_list.append((f"  {glob_pattern}", MonitorValidator.status_symbol(error_msg, is_valid)))

        # Combine into single table with 4 columns
        max_rows = max(len(table_data), len(ignore_list))
        combined_data = []

        for i in range(max_rows):
            row = {}
            if i < len(table_data):
                row["Setting"] = table_data[i]["Setting"]
                row["Value"] = table_data[i]["Value"]
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

        return 0

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
    # Helper function for modifying config lists

    def _modify_monitor_list(display, list_name: str, value: str, operation: str, resolve_path: bool = True) -> int:
        """Modify a monitor config list (add/remove)."""
        config_path = get_config_path()

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
        config_path = get_config_path()

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
        config_path = get_config_path()

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
        config_path = get_config_path()

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

    # DB command: query databases by layer
    dbp = cli_db.setup_db_parser(sub)

    # MCP server command
    mcp = sub.add_parser("mcp", help="MCP (Model Context Protocol) server for AI integration")
    mcpsub = mcp.add_subparsers(dest="mcp_cmd")

    mcprun = mcpsub.add_parser("run", help="Start MCP server (stdio transport)")
    def _mcp_run(args: argparse.Namespace) -> int:
        """Start MCP server for AI integration."""
        from .mcp_server import main as mcp_main
        mcp_main()
        return 0
    mcprun.set_defaults(func=_mcp_run)

    # Simplified CLI — top-level groups: config/service/monitor/extract/index/related/db/mcp

    args = parser.parse_args(argv)

    # Preserve requested display for legacy handling
    args.display_requested = args.display
    mapped_display = args.display
    if mapped_display in DISPLAY_CHOICES_LEGACY:
        mapped_display = "cli" if mapped_display != "mcp" else mapped_display
    args.display_obj = get_display(mapped_display)

    if not hasattr(args, "func"):
        # If a group was selected without subcommand, show that group's help
        try:
            cmd = getattr(args, 'cmd', None)
            if cmd == 'config':
                cfg.print_help()
                return 2
            if cmd == 'service':
                svc.print_help()
                return 2
            if cmd == 'monitor':
                mon.print_help()
                return 2
            if cmd == 'db':
                dbp.print_help()
                return 2
            if cmd == 'mcp':
                mcp.print_help()
                return 2
        except Exception:
            pass
        parser.print_help()
        return 2

    res = args.func(args)
    return 0 if res is None else res


if __name__ == "__main__":
    raise SystemExit(main())
