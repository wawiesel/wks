"""
WKS command-line interface.

Provides simple commands for managing the daemon, config, and local MongoDB.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple
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


def daemon_status(_: argparse.Namespace) -> int:
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
    # Start as background process: python -m wks.daemon
    env = os.environ.copy()
    python = sys.executable
    log_dir = Path.home() / ".wks"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "daemon.log"
    with open(log_file, "ab", buffering=0) as lf:
        # Detach: create a new session
        kwargs = {
            "stdout": lf,
            "stderr": lf,
            "stdin": subprocess.DEVNULL,
            "start_new_session": True,
            "env": env,
        }
        try:
            p = subprocess.Popen([python, "-m", "wks.daemon"], **kwargs)
        except Exception as e:
            print(f"Failed to start daemon: {e}")
            sys.exit(1)
    print(f"WKS daemon started (PID {p.pid}). Log: {log_file}")


def daemon_stop(_: argparse.Namespace):
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


def mongo_cmd(args: argparse.Namespace):
    # Try to use the helper script if available; else attempt direct mongod
    script = Path(__file__).resolve().parents[1] / "bin" / "wks-mongo"
    if script.exists():
        try:
            subprocess.check_call([str(script), args.action])
            return
        except subprocess.CalledProcessError as e:
            print(f"wks-mongo {args.action} failed: {e}")
            sys.exit(e.returncode)
    # Fallback minimal start/stop/status using mongod
    dbroot = Path.home() / ".wks" / "mongodb"
    dbpath = dbroot / "db"
    logfile = dbroot / "mongod.log"
    pidfile = dbroot / "mongod.pid"
    port = 27027
    def is_running() -> bool:
        if pidfile.exists():
            try:
                pid = int(pidfile.read_text().strip())
                return _pid_running(pid)
            except Exception:
                return False
        return False
    if args.action == "start":
        if is_running():
            print(f"mongod already running (PID {pidfile.read_text().strip()})")
            return
        dbpath.mkdir(parents=True, exist_ok=True)
        if not shutil.which("mongod"):
            print("mongod not found; install MongoDB Community edition")
            sys.exit(1)
        subprocess.check_call([
            "mongod", "--dbpath", str(dbpath), "--logpath", str(logfile),
            "--fork", "--bind_ip", "127.0.0.1", "--port", str(port)
        ])
        # Try to capture PID
        try:
            pid = subprocess.check_output(["pgrep", "-f", f"mongod .*--dbpath {dbpath}"]).decode().splitlines()[0]
            pidfile.write_text(pid)
            print(f"Started mongod (PID {pid}) at {dbpath}")
        except Exception:
            print(f"Started mongod; check log at {logfile}")
    elif args.action == "stop":
        if is_running():
            pid = int(pidfile.read_text().strip())
            try:
                os.kill(pid, signal.SIGTERM)
                print(f"Stopped mongod (PID {pid})")
                pidfile.unlink(missing_ok=True)
            except Exception as e:
                print(f"Failed to stop mongod: {e}")
        else:
            print("mongod is not running")
    elif args.action == "status":
        if is_running():
            print(f"mongod running (PID {pidfile.read_text().strip()}) on port 27027")
        else:
            print("mongod is not running")
    elif args.action == "log":
        if logfile.exists():
            subprocess.call(["tail", "-f", str(logfile)])
        else:
            print(f"No log at {logfile}")
    else:
        print("Unknown action; use start|stop|status|log")


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
    mongo_uri = sim_cfg.get("mongo_uri", 'mongodb://localhost:27027/')
    database = sim_cfg.get("database", 'wks_similarity')
    collection = sim_cfg.get("collection", 'file_embeddings')

    def _init():
        return SimilarityDB(database_name=database, collection_name=collection, mongo_uri=mongo_uri, model_name=model)

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


def _iter_files(paths: List[str], include_exts: List[str]) -> List[Path]:
    files: List[Path] = []
    for p in paths:
        pp = Path(p).expanduser()
        if pp.is_file():
            if not include_exts or pp.suffix.lower() in include_exts:
                files.append(pp)
        elif pp.is_dir():
            for x in pp.rglob('*'):
                if x.is_file() and (not include_exts or x.suffix.lower() in include_exts):
                    files.append(x)
    return files


def sim_index_cmd(args: argparse.Namespace) -> int:
    db = _load_similarity_db()
    if not db:
        return 1
    cfg = load_config()
    include_exts = [e.lower() for e in (cfg.get('similarity', {}).get('include_extensions') or [".md", ".txt", ".py", ".ipynb", ".tex"]) ]
    files = _iter_files(args.paths, include_exts)
    if not files:
        print("No files to index (check paths/extensions)")
        return 0
    added = 0
    skipped = 0
    for f in files:
        try:
            if db.add_file(f):
                added += 1
            else:
                skipped += 1
        except Exception as e:
            print(f"Failed to index {f}: {e}")
    print(f"Indexed {added} file(s), skipped {skipped} (unchanged or not text)")
    stats = db.get_stats()
    print(f"DB: {stats['database']}.{stats['collection']} total_files={stats['total_files']}")
    return 0


def sim_query_cmd(args: argparse.Namespace) -> int:
    db = _load_similarity_db()
    if not db:
        return 1
    limit = int(args.top)
    minsim = float(args.min)
    try:
        if args.path:
            results = db.find_similar(query_path=Path(args.path).expanduser(), limit=limit, min_similarity=minsim, mode=args.mode)
        elif args.text:
            results = db.find_similar(query_text=args.text, limit=limit, min_similarity=minsim, mode=args.mode)
        else:
            print("Provide --path or --text")
            return 2
    except Exception as e:
        print(f"Query failed: {e}")
        return 1
    if args.json:
        import json as _json
        print(_json.dumps([{"path": p, "score": s} for p, s in results], indent=2))
    else:
        for p, s in results:
            print(f"{s:0.3f}  {p}")
    return 0


def sim_stats_cmd(_: argparse.Namespace) -> int:
    db = _load_similarity_db()
    if not db:
        return 1
    stats = db.get_stats()
    print(f"database: {stats['database']}")
    print(f"collection: {stats['collection']}")
    print(f"total_files: {stats['total_files']}")
    return 0


def _project_root_for(p: Path) -> Tuple[str, Path]:
    """Classify and return the project/document/deadline root for a path.

    Returns: (kind, root_path) where kind in {project, documents, deadlines, other}
    """
    home = Path.home()
    kind = 'other'
    root = p
    try:
        rel = p.resolve().relative_to(home)
        parts = list(rel.parts)
        if parts:
            first = parts[0]
            # Project like ~/YYYY-Name
            import re as _re
            if _re.match(r"^\d{4}-[^/]+$", first):
                kind = 'project'
                root = home / first
            elif first == 'Documents' and len(parts) >= 2:
                kind = 'documents'
                root = home / 'Documents' / parts[1]
            elif first == 'deadlines' and len(parts) >= 2:
                kind = 'deadlines'
                root = home / 'deadlines' / parts[1]
            else:
                kind = 'other'
                # Use first-level dir (if any) as root
                root = home / first
    except Exception:
        kind = 'other'
        root = p
    return kind, root


def _short(p: Path) -> str:
    try:
        rel = p.resolve().relative_to(Path.home())
        return f"~/{rel}"
    except Exception:
        return str(p)


def sim_route_cmd(args: argparse.Namespace) -> int:
    db = _load_similarity_db()
    if not db:
        return 1
    qpath = Path(args.path).expanduser()
    top = int(args.top)
    minsim = float(args.min)
    try:
        results = db.find_similar(query_path=qpath, limit=top, min_similarity=minsim, mode=args.mode)
    except Exception as e:
        print(f"Route failed: {e}")
        return 1
    if not results:
        print("No similar files found; consider indexing more content with 'wks sim index'")
        return 0
    # Aggregate by project/document/deadline root
    agg: Dict[Path, Dict[str, Any]] = {}
    for path_str, score in results:
        pp = Path(path_str)
        kind, root = _project_root_for(pp)
        rec = agg.setdefault(root, {"score": 0.0, "kind": kind, "hits": []})
        rec["score"] += float(score)
        rec["hits"].append({"path": path_str, "score": float(score)})

    # Rank by aggregate score
    ranked = sorted(((root, data) for root, data in agg.items()), key=lambda x: x[1]["score"], reverse=True)
    suggestions = []
    for root, data in ranked[: args.max_targets]:
        suggestions.append({
            "target": _short(root),
            "kind": data["kind"],
            "score": round(float(data["score"]), 6),
            "hits": data["hits"][: args.evidence],
        })

    if args.json:
        import json as _json
        print(_json.dumps({
            "query": _short(qpath),
            "suggestions": suggestions
        }, indent=2))
    else:
        print(f"Query: {_short(qpath)}\n")
        for s in suggestions:
            print(f"{s['score']:0.3f}  [{s['kind']}]  {s['target']}")
            for h in s["hits"]:
                print(f"    {h['score']:0.3f}  {h['path']}")
    return 0


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


def sim_backfill_cmd(args: argparse.Namespace) -> int:
    db = _load_similarity_db()
    if not db:
        return 1
    cfg = load_config()
    mon = cfg.get('monitor', {})
    roots = [Path(p).expanduser() for p in (args.paths or mon.get('include_paths') or [str(Path.home())])]
    exclude_roots = [Path(p).expanduser() for p in (mon.get('exclude_paths') or [])]
    ignore_dirnames = list(mon.get('ignore_dirnames') or [])
    ignore_patterns = list(mon.get('ignore_patterns') or [])
    ignore_globs = list(mon.get('ignore_globs') or [])
    include_exts = [e.lower() for e in (cfg.get('similarity', {}).get('include_extensions') or [])]

    start = time.time()
    considered = 0
    indexed = 0
    skipped = 0
    for root in roots:
        if any(_is_within(root, ex) for ex in exclude_roots):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dpath = Path(dirpath)
            # Prune excluded/ignored directories in-place
            # Remove any dirnames that should be skipped
            pruned = []
            for i in list(dirnames):
                sub = dpath / i
                if any(_is_within(sub, ex) for ex in exclude_roots) or _should_skip_dir(sub, ignore_dirnames):
                    pruned.append(i)
            for name in pruned:
                try:
                    dirnames.remove(name)
                except ValueError:
                    pass
            # Process files
            for fname in filenames:
                p = dpath / fname
                if _should_skip_file(p, ignore_patterns, ignore_globs):
                    continue
                if include_exts and p.suffix.lower() not in include_exts:
                    continue
                considered += 1
                try:
                    if db.add_file(p):
                        indexed += 1
                    else:
                        skipped += 1
                except Exception:
                    skipped += 1
            # Optional limit
            if args.limit and considered >= args.limit:
                break
        if args.limit and considered >= args.limit:
            break
    elapsed = time.time() - start
    summary = {
        "roots": [r.as_posix() for r in roots],
        "considered": considered,
        "indexed": indexed,
        "skipped": skipped,
        "seconds": round(elapsed, 3),
    }
    if args.json:
        import json as _json
        print(_json.dumps(summary, indent=2))
    else:
        print(f"Roots: {', '.join(summary['roots'])}")
        print(f"Considered: {considered}  Indexed: {indexed}  Skipped: {skipped}  Time: {elapsed:0.2f}s")
    return 0


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


def obs_connect_cmd(args: argparse.Namespace) -> int:
    vault = _load_vault()
    vault.ensure_structure()
    project_path = Path(args.path).expanduser()
    if not project_path.exists() or not project_path.is_dir():
        print(f"Not a directory: {project_path}")
        return 2
    # Create/update project note
    note = vault.create_project_note(project_path, status=args.status or 'Active', description=args.description)
    links = vault.link_project(project_path)
    vault.log_file_operation('created', project_path, details='Connected project to Obsidian (note + links).')
    if args.json:
        import json as _json
        print(_json.dumps({
            "project": project_path.as_posix(),
            "note": note.as_posix(),
            "links": [p.as_posix() for p in links]
        }, indent=2))
    else:
        print(f"Connected: {project_path}\n  Note: {note}\n  Links: {len(links)}")
    return 0


def debug_match_cmd(args: argparse.Namespace) -> int:
    cfg = load_config()
    mon = cfg.get('monitor', {})
    include_paths = [Path(p).expanduser().resolve() for p in (mon.get('include_paths') or [str(Path.home())])]
    exclude_paths = [Path(p).expanduser().resolve() for p in (mon.get('exclude_paths') or [])]
    ignore_dirnames = list(mon.get('ignore_dirnames') or [])
    ignore_globs = list(mon.get('ignore_globs') or [])
    p = Path(args.path).expanduser().resolve()

    def is_within(path: Path, base: Path) -> bool:
        try:
            path.relative_to(base)
            return True
        except Exception:
            return False

    reason = None
    decision = 'include'

    # Absolute excludes
    for ex in exclude_paths:
        if is_within(p, ex):
            decision = 'ignore'
            reason = f'exclude_paths: {ex}'
            break

    # Outside include_paths
    if reason is None and include_paths:
        if not any(is_within(p, inc) for inc in include_paths):
            decision = 'ignore'
            reason = 'outside include_paths'

    # Dotfile segments (except .wks)
    if reason is None:
        for part in p.parts:
            if part.startswith('.') and part != '.wks':
                decision = 'ignore'
                reason = f'dot-segment: {part}'
                break

    # Name-based dir ignores
    if reason is None:
        for part in p.parts:
            if part in ignore_dirnames:
                decision = 'ignore'
                reason = f'ignore_dirnames: {part}'
                break

    # Glob ignores
    if reason is None:
        pstr = p.as_posix()
        for g in ignore_globs:
            if fnmatch.fnmatchcase(pstr, g) or fnmatch.fnmatchcase(p.name, g):
                decision = 'ignore'
                reason = f'ignore_globs: {g}'
                break

    out = {
        'path': p.as_posix(),
        'decision': decision,
        'reason': reason or 'included',
        'include_paths': [x.as_posix() for x in include_paths],
        'exclude_paths': [x.as_posix() for x in exclude_paths],
        'ignore_dirnames': ignore_dirnames,
        'ignore_globs': ignore_globs,
    }
    if args.json:
        import json as _json
        print(_json.dumps(out, indent=2))
    else:
        print(f"Path: {out['path']}")
        print(f"Decision: {out['decision']} ({out['reason']})")
    return 0


def obs_init_logs_cmd(args: argparse.Namespace) -> int:
    # Ensure Obsidian structure and initialize logs with a first entry and ActiveFiles snapshot
    vault = _load_vault()
    vault.ensure_structure()
    # No legacy migrations; keep simple

    # Determine tracked files count from monitor state
    cfg = load_config()
    state_path = Path((cfg.get('monitor') or {}).get('state_file', str(Path.home()/'.wks'/'monitor_state.json'))).expanduser()
    tracked = 0
    try:
        if state_path.exists():
            import json as _json
            data = _json.load(open(state_path, 'r'))
            tracked = len(data.get('files') or {})
    except Exception:
        tracked = 0

    # Write an initialization entry to FileOperations
    home = Path.home()
    vault.log_file_operation('initialized', home, details='Initialized Obsidian logs via wks obs init-logs', tracked_files_count=tracked)

    # Update ActiveFiles from current tracker (if present)
    try:
        from .activity import ActivityTracker
        act_cfg = cfg.get('activity', {})
        act_state = Path(act_cfg.get('state_file', str(Path.home()/'.wks'/'activity_state.json'))).expanduser()
        tracker = ActivityTracker(act_state)
        top = tracker.get_top_active_files(limit=getattr(vault, 'active_files_max_rows', 50))
        vault.update_active_files(top)
    except Exception:
        # Create a minimal header if tracker missing
        vault.update_active_files([])

    if args.json:
        import json as _json
        print(_json.dumps({'file_operations': str(vault.file_log_path), 'active_files': str(vault.activity_log_path), 'tracked': tracked}, indent=2))
    else:
        print(f"Initialized logs:\n  {vault.file_log_path}\n  {vault.activity_log_path}\n  Tracked files: {tracked}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wks", description="WKS management CLI")
    sub = parser.add_subparsers(dest="cmd")

    cfg = sub.add_parser("config", help="Config commands")
    cfg_sub = cfg.add_subparsers(dest="cfg_cmd")
    cfg_print = cfg_sub.add_parser("print", help="Print effective config")
    cfg_print.set_defaults(func=print_config)

    d = sub.add_parser("daemon", help="Manage daemon")
    dsub = d.add_subparsers(dest="d_cmd")
    dstart = dsub.add_parser("start", help="Start daemon in background")
    dstart.set_defaults(func=daemon_start)
    dstop = dsub.add_parser("stop", help="Stop daemon")
    dstop.set_defaults(func=daemon_stop)
    dstatus = dsub.add_parser("status", help="Daemon status")
    dstatus.set_defaults(func=daemon_status)

    m = sub.add_parser("mongo", help="Run local MongoDB under ~/.wks")
    m.add_argument("action", choices=["start", "stop", "status", "log"]) 
    m.set_defaults(func=mongo_cmd)

    # Similarity tools for agents
    sim = sub.add_parser("sim", help="Similarity indexing and queries")
    sim_sub = sim.add_subparsers(dest="sim_cmd")

    sim_idx = sim_sub.add_parser("index", help="Index files or directories (recursive) into similarity DB")
    sim_idx.add_argument("paths", nargs="+", help="Files or directories to index")
    sim_idx.set_defaults(func=sim_index_cmd)

    sim_q = sim_sub.add_parser("query", help="Find files similar to a path or text")
    sim_q.add_argument("--path", help="Path to query file")
    sim_q.add_argument("--text", help="Raw text to query")
    sim_q.add_argument("--top", default=10, help="Max results (default 10)")
    sim_q.add_argument("--min", default=0.0, help="Minimum similarity threshold")
    sim_q.add_argument("--mode", choices=["file","chunk"], default="file", help="Comparison mode: file (aggregated) or chunk (max of chunks)")
    sim_q.add_argument("--json", action="store_true", help="Output JSON (path, score)")
    sim_q.set_defaults(func=sim_query_cmd)

    sim_stats = sim_sub.add_parser("stats", help="Similarity database stats")
    sim_stats.set_defaults(func=sim_stats_cmd)

    sim_route = sim_sub.add_parser("route", help="Suggest target folders for a file based on similarity")
    sim_route.add_argument("--path", required=True, help="Path of the file to route")
    sim_route.add_argument("--top", default=20, help="Consider top-N similar files (default 20)")
    sim_route.add_argument("--min", default=0.0, help="Minimum similarity threshold")
    sim_route.add_argument("--max-targets", dest="max_targets", default=5, type=int, help="Max suggestions to return")
    sim_route.add_argument("--evidence", default=5, type=int, help="Include up to N evidence hits per suggestion")
    sim_route.add_argument("--mode", choices=["file","chunk"], default="chunk", help="Use chunk mode for better matching on long files")
    sim_route.add_argument("--json", action="store_true", help="Output JSON with suggestions and evidence")
    sim_route.set_defaults(func=sim_route_cmd)

    sim_back = sim_sub.add_parser("backfill", help="Index existing files under include_paths (or given roots) using config excludes/ignores")
    sim_back.add_argument("paths", nargs='*', help="Optional roots to scan; defaults to monitor.include_paths or ~")
    sim_back.add_argument("--limit", type=int, help="Stop after indexing N files (for testing)")
    sim_back.add_argument("--json", action="store_true", help="Output JSON summary")
    sim_back.set_defaults(func=sim_backfill_cmd)

    obs = sub.add_parser("obs", help="Obsidian helpers")
    obs_sub = obs.add_subparsers(dest="obs_cmd")
    obs_connect = obs_sub.add_parser("connect", help="Connect a project directory to the vault (create note + links)")
    obs_connect.add_argument("--path", required=True, help="Project directory (e.g., ~/2025-MyProject)")
    obs_connect.add_argument("--status", help="Project status (default Active)")
    obs_connect.add_argument("--description", help="Optional note description")
    obs_connect.add_argument("--json", action="store_true", help="JSON output")
    obs_connect.set_defaults(func=obs_connect_cmd)

    dbg = sub.add_parser("debug", help="Debug utilities")
    dbg_sub = dbg.add_subparsers(dest="dbg_cmd")
    dbg_match = dbg_sub.add_parser("match", help="Explain how a path is matched by include/exclude/ignore rules")
    dbg_match.add_argument("path", help="Path to test")
    dbg_match.add_argument("--json", action="store_true", help="JSON output")
    dbg_match.set_defaults(func=debug_match_cmd)

    obs_init = obs_sub.add_parser("init-logs", help="Initialize Obsidian logs (alias of reset-logs)")
    obs_init.add_argument("--json", action="store_true", help="JSON output")
    obs_init.set_defaults(func=obs_init_logs_cmd)

    obs_reset = obs_sub.add_parser("reset-logs", help="Reset Obsidian logs to a clean state (recreate headers)")
    obs_reset.add_argument("--json", action="store_true", help="JSON output")
    obs_reset.set_defaults(func=obs_init_logs_cmd)

    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 2
    res = args.func(args)
    return 0 if res is None else res


if __name__ == "__main__":
    raise SystemExit(main())
