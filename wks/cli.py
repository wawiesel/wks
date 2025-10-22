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


def _agent_label() -> str:
    return "com.wieselquist.wks"


def _agent_plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{_agent_label()}.plist"


def _is_macos() -> bool:
    return platform.system() == "Darwin"


def _launchctl(*args: str) -> int:
    try:
        return subprocess.call(["launchctl", *args])
    except FileNotFoundError:
        return 2


def _agent_installed() -> bool:
    return _agent_plist_path().exists()


def _daemon_start_launchd():
    uid = os.getuid()
    pl = str(_agent_plist_path())
    _launchctl("bootstrap", f"gui/{uid}", pl)
    _launchctl("enable", f"gui/{uid}/{_agent_label()}")
    _launchctl("kickstart", "-k", f"gui/{uid}/{_agent_label()}")


def _daemon_stop_launchd():
    uid = os.getuid()
    _launchctl("bootout", f"gui/{uid}", str(_agent_plist_path()))


def _daemon_status_launchd() -> int:
    uid = os.getuid()
    return subprocess.call(["launchctl", "print", f"gui/{uid}/{_agent_label()}"])


def daemon_status(_: argparse.Namespace) -> int:
    if _is_macos() and _agent_installed():
        rc = _daemon_status_launchd()
        return 0 if rc == 0 else 3
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


def mongo_cmd(args: argparse.Namespace):
    print("MongoDB is managed by the service (wks-service). Manual control removed for simplicity.")
    return 0


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
    # Use required loader so extract engine is configured
    db, _ = _load_similarity_required()
    cfg = load_config()
    include_exts = [e.lower() for e in (cfg.get('similarity', {}).get('include_extensions') or [])]
    files = _iter_files(args.paths, include_exts)
    if not files:
        print("No files to index (check paths/extensions)")
        return 0
    # Prepare vault for writing docs
    vault = _load_vault()
    docs_keep = int((cfg.get('obsidian') or {}).get('docs_keep', 99))
    added = 0
    skipped = 0
    for f in files:
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


def sim_extract_cmd(args: argparse.Namespace) -> int:
    db, sim = _load_similarity_required()
    p = Path(args.path).expanduser()
    if not p.exists():
        print(f"No such file: {p}")
        return 2
    try:
        text = db._read_file_text(p, max_chars=db.max_chars)
    except Exception as e:
        print(f"Extraction failed: {e}")
        return 1
    out = {
        "path": str(p),
        "engine": db.extract_engine,
        "chars": len(text or "") if text else 0,
        "preview": (text or "")[:500]
    }
    if args.json:
        import json as _json
        print(_json.dumps(out, indent=2))
    else:
        print(f"Engine: {out['engine']}  Chars: {out['chars']}\nPreview:\n{out['preview']}")
    return 0


def _collect_md_paths(paths: List[str]) -> List[Path]:
    cfg = load_config()
    mon = cfg.get('monitor', {})
    include_paths = [Path(p).expanduser() for p in (mon.get('include_paths') or [])]
    exclude_paths = [Path(p).expanduser() for p in (mon.get('exclude_paths') or [])]
    ignore_dirnames = set(mon.get('ignore_dirnames') or [])
    def is_within(p: Path, base: Path) -> bool:
        try:
            p.resolve().relative_to(base.resolve())
            return True
        except Exception:
            return False
    def skip_dir(p: Path) -> bool:
        for part in p.parts:
            if part.startswith('.') and part != '.wks':
                return True
            if part in ignore_dirnames:
                return True
        return False
    md: List[Path] = []
    if paths:
        queue = []
        for p in paths:
            pp = Path(p).expanduser()
            if pp.is_file() and pp.suffix.lower() == '.md':
                queue.append(pp)
            elif pp.is_dir():
                queue.extend(list(pp.rglob('*.md')))
        for p in queue:
            if any(is_within(p, ex) for ex in exclude_paths) or skip_dir(p.parent):
                continue
            md.append(p)
    else:
        for inc in include_paths:
            if not inc.exists():
                continue
            for p in inc.rglob('*.md'):
                if any(is_within(p, ex) for ex in exclude_paths) or skip_dir(p.parent):
                    continue
                md.append(p)
    return md


def sim_dump_docs_cmd(args: argparse.Namespace) -> int:
    db, _ = _load_similarity_required()
    vault = _load_vault()
    cfg = load_config()
    docs_keep = int((cfg.get('obsidian') or {}).get('docs_keep', 99))
    md_files = _collect_md_paths(args.paths or [])
    if not md_files:
        print('No Markdown files found to dump')
        return 0
    dumped = 0
    for p in md_files:
        try:
            txt = db._read_file_text(p, max_chars=db.max_chars) or ''
            # Use DB hasher to compute content hash
            ch = db._compute_hash(txt)
            vault.write_doc_text(ch, p, txt, keep=docs_keep)
            dumped += 1
        except Exception as e:
            print(f'Failed to dump {p}: {e}')
    print(f'Dumped {dumped} Markdown file(s) to ~/obsidian/WKS/Docs')
    return 0


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


def names_route_cmd(args: argparse.Namespace) -> int:
    p = Path(args.path).expanduser()
    if not p.exists():
        print(f"No such path: {p}")
        return 2
    scope = args.scope
    # Determine date
    if args.date:
        try:
            date = _normalize_date(args.date)
        except Exception as e:
            print(f"Invalid --date: {e}")
            return 2
    else:
        date = _date_for_scope(scope, p)
    # Determine name
    if args.name:
        name = _sanitize_name(args.name)
    else:
        stem = p.stem if p.is_file() else p.name
        name = _sanitize_name(stem)
    folder = f"{date}-{name}"
    # Determine base output
    if scope == 'project':
        base = Path.home()
    elif scope == 'document':
        base = Path.home() / 'Documents'
    else:
        base = Path.home() / 'deadlines'
    full = base / folder
    if args.json:
        import json as _json
        print(_json.dumps({
            'scope': scope,
            'date': date,
            'name': name,
            'folder': folder,
            'path': str(full),
        }, indent=2))
    else:
        print(f"{full}")
    return 0


def names_check_cmd(args: argparse.Namespace) -> int:
    roots = [Path(p).expanduser() for p in (args.roots or [])]
    if not roots:
        # Default to scanning include_paths top-level dirs
        cfg = load_config()
        mon = cfg.get('monitor', {})
        roots = [Path(p).expanduser() for p in (mon.get('include_paths') or [])]
    problems = []
    for root in roots:
        if not root.exists() or not root.is_dir():
            continue
        for entry in root.iterdir():
            if not entry.is_dir():
                continue
            name = entry.name
            m = _FOLDER_RE.match(name)
            if not m:
                problems.append((str(entry), 'does not match DATE-NAME rule'))
                continue
            date, nm = m.groups()
            if not _DATE_RE.match(date):
                problems.append((str(entry), f'invalid DATE: {date}'))
            if '-' in nm:
                problems.append((str(entry), 'NAME contains hyphens'))
    if args.json:
        import json as _json
        print(_json.dumps([
            {'path': p, 'problem': why} for p, why in problems
        ], indent=2))
    else:
        if not problems:
            print('No naming problems found.')
        else:
            for p, why in problems:
                print(f"{p}: {why}")
    return 0


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


def _infer_year_from_dir(d: Path) -> int:
    try:
        latest = 0
        for p in d.rglob('*'):
            try:
                if p.is_file():
                    m = int(p.stat().st_mtime)
                    if m > latest:
                        latest = m
            except Exception:
                continue
        if latest > 0:
            import time as _time
            return int(_time.strftime('%Y', _time.localtime(latest)))
    except Exception:
        pass
    from datetime import datetime as _dt
    return int(_dt.now().strftime('%Y'))


def _plan_project_fixes() -> list[tuple[Path, Path]]:
    home = Path.home()
    plans: list[tuple[Path, Path]] = []
    for entry in home.iterdir():
        if not entry.is_dir():
            continue
        name = entry.name
        # Only operate on project-like dirs: YYYY-Name
        m = re.match(r'^(\d{4})-(.+)$', name)
        if not m:
            continue
        year, namestr = m.group(1), m.group(2)
        bad = False
        new_year = year
        # Validate year
        if not re.match(r'^20\d{2}$', year):
            new_year = str(_infer_year_from_dir(entry))
            bad = True
        # Validate namestring (no hyphens allowed; only [A-Za-z0-9_])
        new_name = namestr
        if '-' in namestr or not re.match(r'^[A-Za-z0-9_]+$', namestr):
            new_name = _pascalize_name(namestr)
            bad = True
        if bad:
            dst = home / f"{new_year}-{new_name}"
            if dst != entry:
                plans.append((entry, dst))
    return plans


def names_fix_cmd(args: argparse.Namespace) -> int:
    scope = args.scope
    if scope != 'project':
        print("Only --scope project is implemented right now.")
        return 2
    plans = _plan_project_fixes()
    if not plans:
        print("No project naming fixes needed.")
        return 0
    if not args.apply:
        print("Planned renames (dry run):")
        for src, dst in plans:
            print(f"- {src} -> {dst}")
        print("Run again with --apply to perform changes.")
        return 0
    # Apply
    vault = _load_vault()
    vault.ensure_structure()
    applied = 0
    skipped = 0
    for src, dst in plans:
        if dst.exists():
            print(f"Skip (exists): {dst}")
            skipped += 1
            continue
        try:
            os.rename(src, dst)
            # Update vault wiki links referencing this path
            try:
                vault.update_vault_links_on_move(src, dst)
            except Exception:
                pass
            # Recreate common file links and cleanup broken
            try:
                vault.link_project(dst)
            except Exception:
                pass
            applied += 1
            print(f"Renamed: {src.name} -> {dst.name}")
        except Exception as e:
            print(f"Failed to rename {src} -> {dst}: {e}")
            skipped += 1
    try:
        removed = vault.cleanup_broken_links()
        if removed:
            print(f"Cleaned {removed} broken links in vault.")
    except Exception:
        pass
    print(f"Applied {applied}, skipped {skipped}.")
    return 0


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
    # Extraction config (explicit)
    ext = cfg.get('extract')
    if ext is None or 'engine' not in ext or 'ocr' not in ext or 'timeout_secs' not in ext:
        print("Fatal: 'extract.engine', 'extract.ocr', and 'extract.timeout_secs' are required in config")
        raise SystemExit(2)
    db = SimilarityDB(
        database_name=sim['database'],
        collection_name=sim['collection'],
        mongo_uri=sim['mongo_uri'],
        model_name=sim['model'],
        model_path=sim.get('model_path'),
        offline=bool(sim.get('offline', False)),
        max_chars=int(sim['max_chars']),
        chunk_chars=int(sim['chunk_chars']),
        chunk_overlap=int(sim['chunk_overlap']),
        extract_engine=ext['engine'],
        extract_ocr=bool(ext['ocr']),
        extract_timeout_secs=int(ext['timeout_secs']),
    )
    return db, sim


def sim_migrate_cmd(args: argparse.Namespace) -> int:
    db, sim = _load_similarity_required()
    cfg = load_config()
    vault = _load_vault()
    docs_keep = int((cfg.get('obsidian') or {}).get('docs_keep', 99))
    limit = args.limit
    prune = args.prune_missing
    count = 0
    updated = 0
    removed = 0
    for doc in db.collection.find():
        path = Path(doc.get('path',''))
        if not path:
            continue
        if not path.exists():
            if prune:
                try:
                    db.remove_file(path)
                    removed += 1
                except Exception:
                    pass
            continue
        try:
            # Force re-embed regardless of content_hash
            changed = db.add_file(path, force=True)
            if changed:
                updated += 1
                rec = db.get_last_add_result() or {}
                ch = rec.get('content_hash')
                txt = rec.get('text')
                if ch and txt is not None:
                    try:
                        vault.write_doc_text(ch, path, txt, keep=docs_keep)
                    except Exception:
                        pass
        except Exception:
            pass
        count += 1
        if limit and count >= limit:
            break
    out = {"considered": count, "updated": updated, "removed": removed}
    if args.json:
        import json as _json
        print(_json.dumps(out, indent=2))
    else:
        print(f"Considered: {count}  Updated: {updated}  Removed: {removed}")
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
    drestart = dsub.add_parser("restart", help="Restart daemon")
    drestart.set_defaults(func=daemon_restart)

    # Optional install/uninstall on macOS (hide behind help)
    def _launchctl(*args: str) -> int:
        try:
            return subprocess.call(["launchctl", *args])
        except FileNotFoundError:
            print("launchctl not found; macOS only")
            return 2

    def _plist_path() -> Path:
        return Path.home()/"Library"/"LaunchAgents"/"com.wieselquist.wks.plist"

    def daemon_install(_: argparse.Namespace):
        if platform.system() != "Darwin":
            print("install is macOS-only (launchd)")
            return
        pl = _plist_path()
        pl.parent.mkdir(parents=True, exist_ok=True)
        log_dir = Path.home()/".wks"
        log_dir.mkdir(exist_ok=True)
        python = sys.executable
        proj_root = Path(__file__).resolve().parents[1]
        xml = f"""
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.wieselquist.wks</string>
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
        _launchctl("bootout", f"gui/{os.getuid()}", str(pl))
        _launchctl("bootstrap", f"gui/{os.getuid()}", str(pl))
        _launchctl("enable", f"gui/{os.getuid()}/com.wieselquist.wks")
        _launchctl("kickstart", "-k", f"gui/{os.getuid()}/com.wieselquist.wks")
        print(f"Installed and started: {pl}")

    def daemon_uninstall(_: argparse.Namespace):
        if platform.system() != "Darwin":
            print("uninstall is macOS-only (launchd)")
            return
        pl = _plist_path()
        _launchctl("bootout", f"gui/{os.getuid()}", str(pl))
        try:
            pl.unlink()
        except Exception:
            pass
        print("Uninstalled.")

    dinst = dsub.add_parser("install", help="Install launchd agent (macOS)")
    dinst.set_defaults(func=daemon_install)
    duninst = dsub.add_parser("uninstall", help="Uninstall launchd agent (macOS)")
    duninst.set_defaults(func=daemon_uninstall)

    # Mongo is managed by the service; CLI subcommand retained to print message
    # for users accustomed to the old flow.
    m = sub.add_parser("mongo", help="(Deprecated) MongoDB is managed by the wks-service")
    m.add_argument("action", nargs='?', default='status')
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

    sim_mig = sim_sub.add_parser("migrate", help="Recompute embeddings for all files in the DB with current settings; optional prune missing")
    sim_mig.add_argument("--prune-missing", action="store_true", help="Remove DB entries for missing files")
    sim_mig.add_argument("--limit", type=int, help="Stop after N files")
    sim_mig.add_argument("--json", action="store_true", help="JSON summary output")
    sim_mig.set_defaults(func=sim_migrate_cmd)

    sim_ext = sim_sub.add_parser("extract", help="Extract text from a file with the configured engine")
    sim_ext.add_argument("--path", required=True, help="Path to the file")
    sim_ext.add_argument("--json", action="store_true", help="JSON output")
    sim_ext.set_defaults(func=sim_extract_cmd)

    sim_dump = sim_sub.add_parser("dump-docs", help="Write Docling (or configured engine) dumps of Markdown files to ~/obsidian/WKS/Docs")
    sim_dump.add_argument("paths", nargs='*', help="Files or directories. If omitted, scans monitor.include_paths")
    sim_dump.set_defaults(func=sim_dump_docs_cmd)

    sim_demo = sim_sub.add_parser("demo", help="Compute similarities among given files without using the DB (offline embeddings demo)")
    sim_demo.add_argument("paths", nargs="+", help="Files or directories to include (.md/.txt/.py/.tex)")
    sim_demo.add_argument("--top", type=int, default=6, help="Show top-N most similar pairs (default 6)")
    def _sim_demo_cmd(args: argparse.Namespace) -> int:
        # Initialize model using config (offline if set)
        cfg = load_config()
        sim_cfg = cfg.get('similarity', {})
        model = sim_cfg.get('model', 'sentence-transformers/all-MiniLM-L6-v2')
        model_path = sim_cfg.get('model_path')
        offline = bool(sim_cfg.get('offline', False))
        import os as _os
        if offline:
            _os.environ.setdefault('HF_HUB_OFFLINE', '1')
            _os.environ.setdefault('TRANSFORMERS_OFFLINE', '1')
        try:
            from sentence_transformers import SentenceTransformer
        except Exception as e:
            print(f"sentence-transformers not available: {e}")
            return 2
        target = (model_path or model).strip()
        try:
            embedder = SentenceTransformer(target)
        except Exception as e:
            print(f"Failed to load model '{target}': {e}")
            return 2
        # Collect files
        include_exts = {'.md', '.txt', '.py', '.tex'}
        files: list[Path] = []
        for p in args.paths:
            pp = Path(p).expanduser()
            if pp.is_file() and pp.suffix.lower() in include_exts:
                files.append(pp)
            elif pp.is_dir():
                for x in pp.rglob('*'):
                    if x.is_file() and x.suffix.lower() in include_exts:
                        files.append(x)
        if len(files) < 2:
            print("Need at least two text-like files (.md/.txt/.py/.tex)")
            return 2
        # Read texts (simple reader)
        items: list[tuple[Path,str]] = []
        for f in files:
            try:
                text = f.read_text(encoding='utf-8', errors='ignore')
            except Exception:
                text = None
            if text and len(text.strip()) >= max(10, int(sim_cfg.get('min_chars', 10))):
                items.append((f, text))
        if len(items) < 2:
            print("Not enough textual content to compare.")
            return 0
        # Encode and compute pairwise cosine similarities
        from numpy import dot
        from numpy.linalg import norm
        import numpy as np
        vecs = embedder.encode([t for _, t in items])
        paths = [p for p, _ in items]
        pairs: list[tuple[float,int,int]] = []
        for i in range(len(vecs)):
            for j in range(i+1, len(vecs)):
                a = np.array(vecs[i]); b = np.array(vecs[j])
                sim = float(dot(a, b) / (norm(a) * norm(b))) if norm(a) and norm(b) else 0.0
                pairs.append((sim, i, j))
        pairs.sort(reverse=True, key=lambda x: x[0])
        top = max(1, int(args.top))
        print("Top similar pairs:\n")
        for sim, i, j in pairs[:top]:
            print(f"{sim:0.3f}  {paths[i].name}  ~  {paths[j].name}")
        return 0
    sim_demo.set_defaults(func=_sim_demo_cmd)

    # Names commands
    n = sub.add_parser("names", help="Naming utilities")
    nsub = n.add_subparsers(dest="names_cmd")

    nroute = nsub.add_parser("route", help="Generate a normalized DATE-NAME folder name for a path")
    nroute.add_argument("--path", required=True, help="Path to file or folder")
    nroute.add_argument("--scope", choices=["project","document","deadline"], default="project")
    nroute.add_argument("--date", help="Explicit DATE (YYYY or YYYY_MM or YYYY_MM_DD)")
    nroute.add_argument("--name", help="Explicit NAME (will be sanitized)")
    nroute.add_argument("--json", action="store_true", help="JSON output")
    nroute.set_defaults(func=names_route_cmd)

    ncheck = nsub.add_parser("check", help="Check directory names under roots for DATE-NAME compliance")
    ncheck.add_argument("roots", nargs='*', help="Roots to scan (defaults to monitor.include_paths top-level)")
    ncheck.add_argument("--json", action="store_true", help="JSON output")
    ncheck.set_defaults(func=names_check_cmd)

    nfix = nsub.add_parser("fix", help="Fix non-conforming names (projects only)")
    nfix.add_argument("--scope", choices=["project"], default="project", help="Scope to fix (projects only for now)")
    nfix.add_argument("--apply", action="store_true", help="Apply changes (default is dry-run)")
    nfix.set_defaults(func=names_fix_cmd)

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

    # Links commands
    from . import links as _links
    lnk = sub.add_parser("links", help="Link organization tools")
    lsub = lnk.add_subparsers(dest="links_cmd")
    ltidy = lsub.add_parser("tidy", help="Organize bare URLs in a Markdown file into categories with titles and blurbs")
    ltidy.add_argument("--source", required=True, help="Path to Markdown file (e.g., ~/obsidian/Topics/2025-AwesomeUrls.md)")
    def _links_tidy_cmd(args: argparse.Namespace) -> int:
        path = Path(args.source).expanduser()
        if not path.exists():
            print(f"No such file: {path}")
            return 2
        out = _links.write_tidy_markdown(path)
        print(f"Updated: {out}")
        return 0
    ltidy.set_defaults(func=_links_tidy_cmd)

    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 2
    res = args.func(args)
    return 0 if res is None else res


if __name__ == "__main__":
    raise SystemExit(main())
