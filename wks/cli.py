"""
WKS command-line interface.

Provides simple commands for managing the daemon, config, and local MongoDB.
"""

from __future__ import annotations

import argparse
import re
import json
import os
import platform
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional
from dataclasses import dataclass
import os
import fnmatch
import time
import shutil


LOCK_FILE = Path.home() / ".wks" / "daemon.lock"


def load_config() -> Dict[str, Any]:
    path = Path.home() / ".wks" / "config.json"
    if path.exists():
        try:
            return json.load(open(path, "r"))
        except Exception as e:
            print(f"Warning: failed to parse {path}: {e}")
    return {}


def print_config(args):
    cfg = load_config()
    print(json.dumps(cfg, indent=2))


def _pid_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


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
    # Collect launchd status and parse key fields for redisplay
    launch_text = ""
    @dataclass
    class LaunchAgentStatus:
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
        last_exit: str = ""
        pid: str = ""

    launch_info: Optional[LaunchAgentStatus] = None
    if _is_macos() and _agent_installed():
        try:
            uid = os.getuid()
            out = subprocess.check_output(["launchctl", "print", f"gui/{uid}/{_agent_label()}"], stderr=subprocess.STDOUT)
            launch_text = out.decode('utf-8', errors='ignore')
            # Parse a few important fields for dashboard (KISS)
            import re as _re
            def _find(pattern, default=""):
                m = _re.search(pattern, launch_text)
                return (m.group(1).strip() if m else default)
            launch_info = LaunchAgentStatus(
                active_count=_find(r"active count =\s*(\d+)"),
                path=_find(r"\n\s*path =\s*(.*)"),
                type=_find(r"\n\s*type =\s*(.*)"),
                state=_find(r"\n\s*state =\s*(.*)"),
                program=_find(r"\n\s*program =\s*(.*)"),
                working_dir=_find(r"\n\s*working directory =\s*(.*)"),
                stdout=_find(r"\n\s*stdout path =\s*(.*)"),
                stderr=_find(r"\n\s*stderr path =\s*(.*)"),
                pid=_find(r"\n\s*pid =\s*(\d+)"),
                runs=_find(r"\n\s*runs =\s*(\d+)"),
                last_exit=_find(r"\n\s*last exit code =\s*(\d+)"),
            )
            # Parse arguments block (first block only)
            try:
                args_block = _re.search(r"arguments = \{([^}]*)\}", launch_text, _re.DOTALL)
                if args_block:
                    lines = [ln.strip() for ln in args_block.group(1).splitlines() if ln.strip()]
                    if launch_info:
                        launch_info.arguments = " ".join(lines)
            except Exception:
                pass
        except Exception as e:
            launch_text = f"(launchctl print unavailable: {e})\n"
    # Try to read health
    health_path = Path.home()/'.wks'/'health.json'
    health = {}
    try:
        if health_path.exists():
            import json as _json
            health = _json.load(open(health_path, 'r'))
    except Exception:
        health = {}
    dis = getattr(args, 'display', 'rich')
    use_rich = (dis == 'rich') or (dis == 'auto')
    # Fallback simple status text
    if not health:
        out = []
        if LOCK_FILE.exists():
            try:
                pid = int(LOCK_FILE.read_text().strip().splitlines()[0])
                out.append(f"WKS daemon: running (PID {pid})")
            except Exception:
                out.append("WKS daemon: lock present (unknown PID)")
        else:
            out.append("WKS daemon: not running")
        print("\n".join(out))
        return 0 if LOCK_FILE.exists() else 3
    # Pretty dashboard
    try:
        from rich.console import Console
        from rich.table import Table
        from rich.panel import Panel
        from rich.columns import Columns
        from rich.text import Text
        if use_rich:
            # Metrics panel
            t = Table(show_header=True, header_style="bold cyan")
            t.add_column("Metric", style="bold")
            t.add_column("Value")
            ok_flag = 'true' if not health.get('last_error') else 'false'
            rows = [
                ("Heartbeat", health.get('heartbeat_iso','')),
                ("Uptime", health.get('uptime_hms','')),
                ("PID", str(health.get('pid',''))),
                ("Beats/min", str(health.get('avg_beats_per_min',''))),
                ("Pending deletes", str(health.get('pending_deletes',''))),
                ("Pending mods", str(health.get('pending_mods',''))),
                ("OK", ok_flag),
                ("Lock", str(health.get('lock_present')).lower()),
            ]
            for k, v in rows:
                t.add_row(k, v)

            panels = [Panel(t, title="WKS Service", border_style="green" if ok_flag=='true' else "red")]

            # Launchd parsed panel (structured summary)
            if launch_info is not None:
                tl = Table(show_header=True, header_style="bold blue")
                tl.add_column("Key", style="bold")
                tl.add_column("Value")
                for key, val in [
                    ('State', launch_info.state),
                    ('Active Count', launch_info.active_count),
                    ('PID', launch_info.pid),
                    ('Program', launch_info.program),
                    ('Arguments', launch_info.arguments),
                    ('Working Dir', launch_info.working_dir),
                    ('Stdout', launch_info.stdout),
                    ('Stderr', launch_info.stderr),
                    ('Runs', launch_info.runs),
                    ('Last Exit', launch_info.last_exit),
                    ('Path', launch_info.path),
                    ('Type', launch_info.type),
                ]:
                    if val:
                        tl.add_row(key, val)
                panels.append(Panel(tl, title="Launch Agent", border_style="blue"))

            # DB stats panel (best-effort)
            try:
                # Fast, non-blocking DB ping (avoid auto-start or long delays)
                from pymongo import MongoClient as _MC
                cfg = load_config(); sim = cfg.get('similarity') or {}
                uri = sim.get('mongo_uri','mongodb://localhost:27027/')
                name = sim.get('database','wks_similarity')
                coll = sim.get('collection','file_embeddings')
                client = _MC(uri, serverSelectionTimeoutMS=500, connectTimeoutMS=500)
                client.admin.command('ping')
                total = client[name][coll].count_documents({})
                s = {"database": name, "collection": coll, "total_files": total}
                tdb = Table(show_header=True, header_style="bold magenta")
                tdb.add_column("Key", style="bold")
                tdb.add_column("Value")
                for k in ["database","collection","total_files"]:
                    tdb.add_row(k, str(s.get(k,'')))
                panels.append(Panel(tdb, title="Space DB", border_style="magenta"))
            except SystemExit:
                pass
            except Exception:
                pass

            # Last error panel if any
            if health.get('last_error'):
                err = str(health.get('last_error'))
                panels.append(Panel(Text(err, style="red"), title="Last Error", border_style="red"))

            Console().print(Columns(panels))
            return 0
    except Exception:
        pass
    # Basic text dashboard
    # Basic text dashboard
    if launch_info is not None:
        print("Launch Agent:")
        for key, val in [
            ('state', launch_info.state),
            ('active_count', launch_info.active_count),
            ('pid', launch_info.pid),
            ('program', launch_info.program),
            ('arguments', launch_info.arguments),
            ('working_dir', launch_info.working_dir),
            ('stdout', launch_info.stdout),
            ('stderr', launch_info.stderr),
            ('runs', launch_info.runs),
            ('last_exit', launch_info.last_exit),
            ('path', launch_info.path),
            ('type', launch_info.type),
        ]:
            if val:
                print(f"  {key}: {val}")
    print(f"Heartbeat: {health.get('heartbeat_iso','')}")
    print(f"Uptime:    {health.get('uptime_hms','')}")
    print(f"PID:       {health.get('pid','')}")
    print(f"Beats/min: {health.get('avg_beats_per_min','')}")
    print(f"Pending:   deletes={health.get('pending_deletes',0)} mods={health.get('pending_mods',0)}")
    ok = 'true' if not health.get('last_error') else 'false'
    print(f"OK:        {ok}")
    print(f"Lock:      {str(health.get('lock_present')).lower()}")
    return 0
    if LOCK_FILE.exists():
        try:
            pid_line = LOCK_FILE.read_text().strip().splitlines()[0]
            pid = int(pid_line)
            if _pid_running(pid):
                print(f"WKS daemon is running (PID {pid})")
                return 0
            else:
                print("WKS daemon lock exists but process is not running (stale lock)")
                return 1
        except Exception:
            print("Could not read PID from lock; unknown status")
            return 1
    print("WKS daemon is not running")
    return 3


def daemon_start(_: argparse.Namespace):
    if _is_macos() and _agent_installed():
        _daemon_start_launchd()
        return
    # Start as background process: python -m wks.daemon
    env = os.environ.copy()
    python = sys.executable
    log_dir = Path.home() / ".wks"
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


def daemon_stop(_: argparse.Namespace):
    if _is_macos() and _agent_installed():
        _daemon_stop_launchd()
        return
    if not LOCK_FILE.exists():
        print("WKS daemon is not running")
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


def daemon_restart(_: argparse.Namespace):
    # Prefer launchd restart on macOS if installed
    if _is_macos() and _agent_installed():
        try:
            _daemon_stop_launchd()
        finally:
            _daemon_start_launchd()
        return
    # Fallback: stop then start (background process)
    try:
        daemon_stop(argparse.Namespace())
    except Exception:
        pass
    time.sleep(0.5)
    daemon_start(argparse.Namespace())




# ----------------------------- Similarity CLI ------------------------------ #
def _load_similarity_db() -> Any:
    """Initialize SimilarityDB using config; auto-start local mongod if needed."""
    try:
        from .similarity import SimilarityDB  # type: ignore
    except Exception as e:
        print(f"Similarity not available: {e}")
        return None

    cfg = load_config()
    sim_cfg = cfg.get("similarity", {})
    model = sim_cfg.get("model", 'all-MiniLM-L6-v2')
    model_path = sim_cfg.get("model_path")
    offline = bool(sim_cfg.get("offline", False))
    mongo_uri = sim_cfg.get("mongo_uri", 'mongodb://localhost:27027/')
    database = sim_cfg.get("database", 'wks_similarity')
    collection = sim_cfg.get("collection", 'file_embeddings')

    def _init():
        return SimilarityDB(database_name=database, collection_name=collection, mongo_uri=mongo_uri, model_name=model, model_path=model_path, offline=offline)

    try:
        return _init()
    except Exception as e:
        # Try to start local mongod if using our default URI
        if mongo_uri.startswith("mongodb://localhost:27027") and shutil.which("mongod"):
            dbroot = Path.home() / ".wks" / "mongodb"
            dbpath = dbroot / "db"
            logfile = dbroot / "mongod.log"
            dbpath.mkdir(parents=True, exist_ok=True)
            try:
                subprocess.check_call([
                    "mongod", "--dbpath", str(dbpath), "--logpath", str(logfile),
                    "--fork", "--bind_ip", "127.0.0.1", "--port", "27027"
                ])
                return _init()
            except Exception as e2:
                print(f"Failed to auto-start local mongod: {e2}")
                return None
        print(f"Failed to initialize similarity DB: {e}")
        return None


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

    def _skip(p: Path) -> bool:
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
        if pp.is_file():
            if (not include_exts or pp.suffix.lower() in include_exts) and not _skip(pp):
                out.append(pp)
        else:
            for x in pp.rglob('*'):
                if not x.is_file():
                    continue
                if include_exts and x.suffix.lower() not in include_exts:
                    continue
                if _skip(x):
                    continue
                out.append(x)
    return out

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
    try:
        from .similarity import SimilarityDB  # type: ignore
    except Exception as e:
        print(f"Fatal: SimilarityDB not available: {e}")
        raise SystemExit(2)
    cfg = load_config()
    sim = cfg.get('similarity')
    if sim is None or 'enabled' not in sim:
        print("Fatal: 'similarity.enabled' is required in config")
        raise SystemExit(2)
    if not sim.get('enabled'):
        print("Fatal: similarity.enabled must be true for this operation")
        raise SystemExit(2)
    required = [
        'mongo_uri','database','collection','model',
        'include_extensions','min_chars','max_chars','chunk_chars','chunk_overlap'
    ]
    missing = [k for k in required if k not in sim]
    if missing:
        print("Fatal: missing similarity keys: " + ", ".join([f"similarity.{k}" for k in missing]))
        raise SystemExit(2)
    # Extraction config (docling required)
    ext = cfg.get('extract')
    if ext is None or 'engine' not in ext or 'ocr' not in ext or 'timeout_secs' not in ext:
        print("Fatal: 'extract.engine', 'extract.ocr', and 'extract.timeout_secs' are required in config")
        raise SystemExit(2)
    if str(ext.get('engine')).lower() != 'docling':
        print("Fatal: extract.engine must be 'docling'")
        raise SystemExit(2)
    def _make():
        return SimilarityDB(
            database_name=sim['database'],
            collection_name=sim['collection'],
            mongo_uri=sim['mongo_uri'],
            model_name=sim['model'],
            model_path=sim.get('model_path'),
            offline=bool(sim.get('offline', False)),
            max_chars=int(sim['max_chars']),
            chunk_chars=int(sim['chunk_chars']),
            chunk_overlap=int(sim['chunk_overlap']),
            extract_engine='docling',
            extract_ocr=bool(ext['ocr']),
            extract_timeout_secs=int(ext['timeout_secs']),
        )
    try:
        db = _make()
        return db, sim
    except Exception as e:
        # Auto-start local mongod if URI is localhost:27027 and mongod exists
        try:
            import shutil as _sh, subprocess as _sp, time as _t
            uri = str(sim.get('mongo_uri',''))
            if uri.startswith('mongodb://localhost:27027') and _sh.which('mongod'):
                dbroot = Path.home() / '.wks' / 'mongodb'
                dbpath = dbroot / 'db'
                logfile = dbroot / 'mongod.log'
                dbpath.mkdir(parents=True, exist_ok=True)
                _sp.check_call([
                    'mongod', '--dbpath', str(dbpath), '--logpath', str(logfile),
                    '--fork', '--bind_ip', '127.0.0.1', '--port', '27027'
                ])
                _t.sleep(0.2)
                db = _make()
                return db, sim
        except Exception:
            pass
        print(f"Fatal: failed to initialize similarity DB: {e}")
        raise SystemExit(2)


# migration removed


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
        if part.startswith('.') and part != '.wks':
            return True
    return False


def _should_skip_file(path: Path, ignore_patterns: List[str], ignore_globs: List[str]) -> bool:
    # Dotfiles except .wks
    if path.name.startswith('.') and path.name != '.wks':
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
        print("Fatal: 'vault_path' is required in ~/.wks/config.json")
        raise SystemExit(2)
    obs = cfg.get('obsidian', {})
    base_dir = obs.get('base_dir')
    if not base_dir:
        print("Fatal: 'obsidian.base_dir' is required in ~/.wks/config.json (e.g., 'WKS')")
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
    parser.add_argument(
        "--display",
        choices=["auto", "rich", "basic"],
        default="rich",
        help="Progress display: rich (interactive), basic (line-by-line), or auto",
    )

    # Lightweight progress helpers
    def _make_progress(total: int, display: str):
        from contextlib import contextmanager
        import sys, time

        def _hms(secs: float) -> str:
            secs = max(0, int(secs))
            h = secs // 3600; m = (secs % 3600) // 60; s = secs % 60
            return f"{h:02d}:{m:02d}:{s:02d}"

        use_rich = False
        if display in (None, "auto"):
            # Auto: prefer rich if available and isatty
            try:
                use_rich = sys.stdout.isatty()
            except Exception:
                use_rich = False
        elif display == "rich":
            use_rich = True
        else:
            use_rich = False

        if use_rich:
            try:
                from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeRemainingColumn

                @contextmanager
                def _rp():
                    with Progress(
                        SpinnerColumn(),
                        TextColumn("[bold blue]Working"),
                        BarColumn(bar_width=None),
                        TextColumn("{task.completed}/{task.total}"),
                        TimeRemainingColumn(),
                        TextColumn("• {task.fields[current]}"),
                    ) as progress:
                        task = progress.add_task("task", total=total, current="")
                        class R:
                            def update(self, filename: str, advance: int = 1):
                                progress.update(task, advance=advance, current=filename)
                            def close(self):
                                pass
                        yield R()
                return _rp()
            except Exception:
                pass

        # Basic, line-by-line
        @contextmanager
        def _bp():
            start = time.time()
            done = {"n": 0}
            class B:
                def update(self, filename: str, advance: int = 1):
                    done["n"] += advance
                    n = done["n"]
                    pct = (n/total*100.0) if total else 100.0
                    elapsed = time.time()-start
                    eta = _hms((elapsed/n)*(total-n)) if n>0 and total>n else _hms(0)
                    print(f"[{n}/{total}] {pct:5.1f}% ETA {eta}  {filename}")
                def close(self):
                    pass
            yield B()
        return _bp()

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
        log_dir = Path.home()/".wks"
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
        with _make_progress(total=5, display=getattr(args, 'display', 'auto')) as prog:
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
        with _make_progress(total=4, display=getattr(args, 'display', 'auto')) as prog:
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
        # Clear local agent state (keep config.json)
        try:
            home = Path.home()
            for name in [
                'file_ops.jsonl','monitor_state.json','activity_state.json','health.json',
                'daemon.lock','daemon.log','daemon.error.log'
            ]:
                p = home/'.wks'/name
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
            _db_stats(argparse.Namespace(space=True, time=False, latest=5, display=getattr(args,'display','rich')))
        except Exception:
            pass
        return 0
    svcreset.set_defaults(func=_service_reset)

    # (analyze group was removed)

    # Top-level index command (moved out of analyze)
    idx = sub.add_parser("index", help="Index files or directories (recursive) into similarity DB with progress")
    idx.add_argument("paths", nargs="+", help="Files or directories to index")
    def _index_cmd(args: argparse.Namespace) -> int:
        print("Connecting to DB…")
        db, _ = _load_similarity_required()
        cfg = load_config()
        include_exts = [e.lower() for e in (cfg.get('similarity', {}).get('include_extensions') or [])]
        files = _iter_files(args.paths, include_exts, cfg)
        if not files:
            print("No files to index (check paths/extensions)")
            return 0
        vault = _load_vault()
        docs_keep = int((cfg.get('obsidian') or {}).get('docs_keep', 99))
        added = 0
        skipped = 0
        errors = 0
        with _make_progress(total=len(files), display=getattr(args, 'display', 'auto')) as prog:
            for f in files:
                prog.update(f.name, advance=0)
                try:
                    updated = db.add_file(f)
                    if updated:
                        added += 1
                        rec = db.get_last_add_result() or {}
                        ch = rec.get('content_hash')
                        txt = rec.get('text')
                        if ch and txt is not None:
                            try:
                                vault.write_doc_text(ch, f, txt, keep=docs_keep)
                            except Exception:
                                pass
                    else:
                        skipped += 1
                except Exception:
                    errors += 1
                finally:
                    prog.update(f.name, advance=1)
        print(f"Indexed {added} file(s), skipped {skipped}, errors {errors}")
        try:
            stats = db.get_stats()
            print(f"DB: {stats['database']}.{stats['collection']} total_files={stats['total_files']}")
        except Exception:
            pass
        return 0
    idx.set_defaults(func=_index_cmd)

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
        db, sim = _load_similarity_required()
        try:
            import json as _json
            filt = _json.loads(args.filter or "{}")
            proj = _json.loads(args.projection) if args.projection else None
        except Exception as e:
            print(f"Invalid JSON: {e}")
            return 2
        # Decide target collection by logical DB
        if args.space:
            coll = db.collection  # space.files (embeddings)
            coll_name = 'file_embeddings'
            scope_label = 'space'
        else:
            coll = db.db['file_snapshots']  # time.snapshots
            coll_name = 'file_snapshots'
            scope_label = 'time'
        cur = coll.find(filt, proj)
        if args.sort:
            try:
                fld, dirspec = args.sort.split(':',1)
                direction = 1 if dirspec.lower().startswith('asc') else -1
                cur = cur.sort(fld, direction)
            except Exception:
                pass
        if args.limit:
            cur = cur.limit(int(args.limit))
        # Output formatting per display
        dis = getattr(args, 'display', 'rich')
        use_rich = (dis == 'rich') or (dis == 'auto')
        try:
            from rich.console import Console
            from rich.table import Table
            if use_rich:
                title = f"[{scope_label}] {coll_name} query"
                t = Table(title=title)
                t.add_column("#", justify="right")
                t.add_column("doc")
                for i, doc in enumerate(cur, 1):
                    t.add_row(str(i), str(doc))
                Console().print(t)
                return 0
        except Exception:
            pass
        # basic
        for i, doc in enumerate(cur, 1):
            print(f"[{i}] {doc}")
        return 0
    dbq.set_defaults(func=_db_query)

    dbs = dbsub.add_parser("stats", help="Print basic DB stats and optionally list latest files")
    scope2 = dbs.add_mutually_exclusive_group()
    scope2.add_argument("--space", action="store_true", help="Stats for the space DB")
    scope2.add_argument("--time", action="store_true", help="Stats for the time DB")
    dbs.add_argument("-n", "--latest", type=int, default=0, help="Show the most recent N records")
    def _db_stats(args: argparse.Namespace) -> int:
        # Use a lightweight, fast Mongo client for stats (no model/docling startup)
        from pymongo import MongoClient as _MC
        cfg = load_config(); sim = cfg.get('similarity') or {}
        uri = sim.get('mongo_uri','mongodb://localhost:27027/')
        name = sim.get('database','wks_similarity')
        coll_space = sim.get('collection','file_embeddings')
        client = _MC(uri, serverSelectionTimeoutMS=300, connectTimeoutMS=300)
        try:
            client.admin.command('ping')
        except Exception as e:
            print(f"DB unreachable: {e}")
            return 1
        if args.time:
            coll = client[name]['file_snapshots']
            total = coll.count_documents({})
            print({"database": name, "collection": "file_snapshots", "total_docs": total})
            n = int(getattr(args, 'latest', 0) or 0)
            if n > 0:
                cur = coll.find({}, {"path": 1, "t_new": 1}).sort("t_new_epoch", -1).limit(n)
                dis = getattr(args, 'display', 'rich')
                use_rich = (dis == 'rich') or (dis == 'auto')
                try:
                    from rich.console import Console
                    from rich.table import Table
                    if use_rich:
                        t = Table(title=f"[time] latest {n} snapshots")
                        t.add_column("#", justify="right")
                        t.add_column("t_new")
                        t.add_column("path")
                        for i, doc in enumerate(cur, 1):
                            t.add_row(str(i), str(doc.get('t_new','')), str(doc.get('path','')))
                        Console().print(t)
                    else:
                        for i, doc in enumerate(cur, 1):
                            print(f"[{i}] {doc.get('t_new','')}  {doc.get('path','')}")
                except Exception:
                    for i, doc in enumerate(cur, 1):
                        print(f"[{i}] {doc.get('t_new','')}  {doc.get('path','')}")
            return 0
        else:
            coll = client[name][coll_space]
            total = coll.count_documents({})
            print({"total_files": total, "database": name, "collection": coll_space})
            n = int(getattr(args, 'latest', 0) or 0)
            if n > 0:
                cur = coll.find({}, {"path": 1, "timestamp": 1}).sort("timestamp", -1).limit(n)
                dis = getattr(args, 'display', 'rich')
                use_rich = (dis == 'rich') or (dis == 'auto')
                try:
                    from rich.console import Console
                    from rich.table import Table
                    if use_rich:
                        t = Table(title=f"[space] latest {n} files")
                        t.add_column("#", justify="right")
                        t.add_column("timestamp")
                        t.add_column("path")
                        for i, doc in enumerate(cur, 1):
                            t.add_row(str(i), str(doc.get('timestamp','')), str(doc.get('path','')))
                        Console().print(t)
                    else:
                        for i, doc in enumerate(cur, 1):
                            print(f"[{i}] {doc.get('timestamp','')}  {doc.get('path','')}")
                except Exception:
                    for i, doc in enumerate(cur, 1):
                        print(f"[{i}] {doc.get('timestamp','')}  {doc.get('path','')}")
            return 0
    dbs.set_defaults(func=_db_stats)

    # DB reset: drop Mongo database and remove local mongod files (if any)
    dbr = dbsub.add_parser("reset", help="Drop WKS Mongo databases and local DB files (space/time)")
    def _db_reset(args: argparse.Namespace) -> int:
        cfg = load_config()
        sim = cfg.get('similarity') or {}
        uri = str(sim.get('mongo_uri','mongodb://localhost:27027/'))
        dbname = sim.get('database','wks_similarity')
        # Try to drop DB via pymongo
        try:
            from pymongo import MongoClient as _MC
            client = _MC(uri, serverSelectionTimeoutMS=3000)
            try:
                client.admin.command('ping')
                client.drop_database(dbname)
                print(f"Dropped database: {dbname}")
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
            dbroot = Path.home()/'.wks'/'mongodb'
            if dbroot.exists():
                _sh.rmtree(dbroot, ignore_errors=True)
                print(f"Removed local DB files: {dbroot}")
        except Exception:
            pass
        return 0
    dbr.set_defaults(func=_db_reset)

    # Simplified CLI — top-level groups: config/service/index/db

    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        # If a group was selected without subcommand, show that group's help
        try:
            cmd = getattr(args, 'cmd', None)
            if cmd == 'service':
                svc.print_help()
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
