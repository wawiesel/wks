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


def sim_index_cmd(args: argparse.Namespace) -> int:
    # Use required loader so extract engine is configured
    db, _ = _load_similarity_required()
    cfg = load_config()
    include_exts = [e.lower() for e in (cfg.get('similarity', {}).get('include_extensions') or [])]
    files = _iter_files(args.paths, include_exts, cfg)
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


# sim_stats_cmd removed (not exposed)


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


# sim_extract_cmd removed (superseded by analyze dump)


# _collect_md_paths removed


# sim_dump_docs_cmd removed


# ----------------------------- LLM helpers --------------------------------- #
def _llm_model_from_config() -> str:
    cfg = load_config()
    llm = cfg.get('llm', {}) or {}
    return str(llm.get('model', 'gpt-oss:20b'))


def _ollama_chat(system_prompt: str, user_prompt: str, model: str) -> str:
    try:
        import ollama  # type: ignore
    except Exception as e:
        return f"[LLM unavailable: install 'pip install ollama' and run 'ollama serve']\n{user_prompt}"
    try:
        res = ollama.chat(model=model, messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ])
        return res.get('message', {}).get('content', '').strip() or ''
    except Exception as e:
        return f"[LLM error: {e}]"


def analyze_dump_cmd(args: argparse.Namespace) -> int:
    db, _ = _load_similarity_required()
    vault = _load_vault()
    p = Path(args.path).expanduser()
    if not p.exists():
        print(f"No such file: {p}")
        return 2
    try:
        txt = db._read_file_text(p, max_chars=db.max_chars) or ''
    except Exception as e:
        print(f"Extract failed: {e}")
        return 1
    ch = db._compute_hash(txt)
    vault.write_doc_text(ch, p, txt, keep=int((load_config().get('obsidian') or {}).get('docs_keep', 99)))
    out = {"doc": (Path(load_config().get('vault_path', '~/obsidian')).expanduser() / (load_config().get('obsidian') or {}).get('base_dir','WKS') / 'Docs' / f"{ch}.md").as_posix(), "checksum": ch}
    if args.json:
        import json as _json
        print(_json.dumps(out, indent=2))
    else:
        print(f"Doc: {out['doc']}\nChecksum: {out['checksum']}")
    return 0


def analyze_name_cmd(args: argparse.Namespace) -> int:
    path = Path(args.path).expanduser()
    if not path.exists() or not path.is_dir():
        print(f"Not a directory: {path}")
        return 2
    # Rule-based suggestion
    try:
        date = _date_for_scope('project', path)
    except Exception:
        from datetime import datetime as _dt
        date = _dt.now().strftime('%Y')
    name_sanitized = _sanitize_name(path.name.split('-',1)[-1])
    rule_name = f"{date}-{name_sanitized}"
    # LLM-based refinement from contents (filenames only to keep quick)
    files = []
    try:
        for p in path.iterdir():
            if p.is_file():
                files.append(p.name)
    except Exception:
        pass
    model = _llm_model_from_config()
    sys_prompt = "You propose concise PascalCase NAMEs for project folders. Only output the NAME token; no date. 1-3 words max."
    user_prompt = f"Based on these file names: {', '.join(files[:40])}\nSuggest a NAME token for folder {path.name}."
    llm_raw = _ollama_chat(sys_prompt, user_prompt, model=model).splitlines()[0].strip()
    if llm_raw.startswith('['):
        llm_name_clean = name_sanitized
    else:
        llm_name_clean = _sanitize_name(llm_raw).replace('_','') or name_sanitized
    final = f"{date}-{llm_name_clean}"
    if args.json:
        import json as _json
        print(_json.dumps({"rule": rule_name, "llm": final, "model": model}, indent=2))
    else:
        print(final)
    return 0


def analyze_dir_cmd(args: argparse.Namespace) -> int:
    path = Path(args.path).expanduser()
    if not path.exists() or not path.is_dir():
        print(f"Not a directory: {path}")
        return 2
    # Respect monitor ignores
    cfg = load_config()
    mon = cfg.get('monitor', {})
    exclude_paths = [Path(p).expanduser().resolve() for p in (mon.get('exclude_paths') or [])]
    ignore_dirnames = set(mon.get('ignore_dirnames') or [])
    ignore_globs = list(mon.get('ignore_globs') or [])
    def _is_within(child: Path, base: Path) -> bool:
        try:
            child.resolve().relative_to(base)
            return True
        except Exception:
            return False
    def _skip(d: Path) -> bool:
        if any(_is_within(d, ex) for ex in exclude_paths):
            return True
        if any(part.startswith('.') and part != '.wks' for part in d.parts):
            return True
        if any(part in ignore_dirnames for part in d.parts):
            return True
        from fnmatch import fnmatchcase
        pstr = d.as_posix()
        if any(fnmatchcase(pstr, g) for g in ignore_globs):
            return True
        return False
    texts = []
    for p in path.rglob('*'):
        try:
            if p.is_dir():
                if _skip(p):
                    continue
                continue
            if p.suffix.lower() not in {'.md', '.txt', '.py', '.tex'}:
                continue
            s = p.read_text(encoding='utf-8', errors='ignore')
            if s and s.strip():
                texts.append(f"# {p.name}\n\n" + s[:1500])
            if len(texts) >= 12:
                break
        except Exception:
            continue
    doc = "\n\n".join(texts) if texts else f"Directory: {path.name} (no readable text files)"
    model = _llm_model_from_config()
    sys_prompt = "Summarize the directory and suggest next steps. Keep it concise and actionable."
    user_prompt = f"Directory: {path}\n\nContent samples:\n\n{doc}"
    out = _ollama_chat(sys_prompt, user_prompt, model=model)
    if args.json:
        import json as _json
        print(_json.dumps({"model": model, "summary": out}, indent=2))
    else:
        print(out)
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


# names_route_cmd removed


def names_check_cmd(args: argparse.Namespace) -> int:
    cfg = load_config()
    mon = cfg.get('monitor', {})
    include_paths = [Path(p).expanduser().resolve() for p in (mon.get('include_paths') or [])]
    exclude_paths = [Path(p).expanduser().resolve() for p in (mon.get('exclude_paths') or [])]
    ignore_dirnames = set(mon.get('ignore_dirnames') or [])
    ignore_globs = list(mon.get('ignore_globs') or [])
    roots = [Path(p).expanduser().resolve() for p in (args.roots or include_paths)]

    def is_within(p: Path, base: Path) -> bool:
        try:
            p.relative_to(base)
            return True
        except Exception:
            return False

    problems = []
    for root in roots:
        if not root.exists() or not root.is_dir():
            continue
        # Only scan immediate children of root
        for entry in root.iterdir():
            if not entry.is_dir():
                continue
            rp = entry.resolve()
            # Apply excludes/ignores
            if any(is_within(rp, ex) for ex in exclude_paths):
                continue
            if any(part.startswith('.') and part != '.wks' for part in rp.parts):
                continue
            if any(part in ignore_dirnames for part in rp.parts):
                continue
            from fnmatch import fnmatchcase
            pstr = rp.as_posix()
            if any(fnmatchcase(pstr, g) for g in ignore_globs):
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
    parser = argparse.ArgumentParser(prog="wks", description="WKS management CLI")
    sub = parser.add_subparsers(dest="cmd")

    cfg = sub.add_parser("config", help="Config commands")
    cfg_sub = cfg.add_subparsers(dest="cfg_cmd")
    cfg_print = cfg_sub.add_parser("print", help="Print effective config")
    cfg_print.set_defaults(func=print_config)

    # Service management (macOS launchd)

    

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

    # Analyze tools (agent helpers)
    analyze = sub.add_parser("analyze", help="Agent helpers: similarity, dump, name, review, check")
    sim_sub = analyze.add_subparsers(dest="an_cmd")

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

    # (stats removed for simplicity)

    sim_route = sim_sub.add_parser("route", help="Suggest target folders for a file based on similarity")
    sim_route.add_argument("--path", required=True, help="Path of the file to route")
    sim_route.add_argument("--top", default=20, help="Consider top-N similar files (default 20)")
    sim_route.add_argument("--min", default=0.0, help="Minimum similarity threshold")
    sim_route.add_argument("--max-targets", dest="max_targets", default=5, type=int, help="Max suggestions to return")
    sim_route.add_argument("--evidence", default=5, type=int, help="Include up to N evidence hits per suggestion")
    sim_route.add_argument("--mode", choices=["file","chunk"], default="chunk", help="Use chunk mode for better matching on long files")
    sim_route.add_argument("--json", action="store_true", help="Output JSON with suggestions and evidence")
    sim_route.set_defaults(func=sim_route_cmd)

    # (backfill removed for simplicity)

    # (migrate removed for simplicity)

    # (extract removed for simplicity)

    # (dump-docs superseded by analyze dump)

    # prune removed; daemon prunes continuously based on config

    # Add non-similarity analyze helpers
    az_dump = sim_sub.add_parser("dump", help="Extract and write a file's text to Obsidian WKS/Docs and print checksum")
    az_dump.add_argument("--path", required=True, help="Path to the file")
    az_dump.add_argument("--json", action="store_true")
    az_dump.set_defaults(func=analyze_dump_cmd)

    az_name = sim_sub.add_parser("name", help="Recommend a better DATE-NAME for a project directory (uses rules + local LLM)")
    az_name.add_argument("--path", required=True)
    az_name.add_argument("--json", action="store_true")
    az_name.set_defaults(func=analyze_name_cmd)

    az_dir = sim_sub.add_parser("review", help="Analyze/summarize a directory using local LLM (ollama)")
    az_dir.add_argument("--path", required=True)
    az_dir.add_argument("--json", action="store_true")
    az_dir.set_defaults(func=analyze_dir_cmd)

    az_check = sim_sub.add_parser("check", help="Check directory names under monitor.include_paths for DATE-NAME compliance")
    az_check.add_argument("roots", nargs='*')
    az_check.add_argument("--json", action="store_true")
    az_check.set_defaults(func=names_check_cmd)

    # Health status
    az_health = sim_sub.add_parser("health", help="Show daemon health status")
    az_health.add_argument("--update", action="store_true", help="Also rebuild the Health.md landing page")
    def _health_cmd(args: argparse.Namespace) -> int:
        path = Path.home()/'.wks'/'health.json'
        import json as _json
        if not path.exists():
            print("Health file not found (daemon may not be running yet)")
            return 1
        try:
            data = _json.load(open(path, 'r'))
        except Exception as e:
            print(f"Failed to read health.json: {e}")
            return 2
        print(_json.dumps(data, indent=2))
        if args.update:
            try:
                cfg = load_config(); obs = cfg.get('obsidian') or {}
                vault = _load_vault()
                # state file from config
                mon = cfg.get('monitor', {})
                state_file = Path(mon.get('state_file', str(Path.home()/'.wks'/'monitor_state.json'))).expanduser()
                vault.write_health_page(state_file=state_file)
                base_dir = obs.get('base_dir') or 'WKS'
                dest = Path(cfg.get('vault_path','~/obsidian')).expanduser()/base_dir/'Health.md'
                print(f"Updated: {dest}")
            except Exception as e:
                print(f"Failed to update Health.md: {e}")
        return 0
    az_health.set_defaults(func=_health_cmd)

    # Simplified CLI — no extra top-level groups beyond config/service/analyze

    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 2
    res = args.func(args)
    return 0 if res is None else res


if __name__ == "__main__":
    raise SystemExit(main())
