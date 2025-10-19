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
from typing import Any, Dict
import re
import shutil
from datetime import datetime


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


def _sanitize_namestring(s: str) -> str:
    # Replace internal hyphens/spaces with underscores to respect single-hyphen rule
    s = s.replace('-', '_')
    s = re.sub(r"\s+", "_", s)
    return s


def _match_document_or_deadline_for_folder(stem: str):
    """Return (kind, folder_name) using the file stem (no extension)."""
    m_dead = re.match(r"^(\d{4})_(\d{2})_(\d{2})-([^/]+)$", stem)
    if m_dead:
        yyyy, mm, dd, rest = m_dead.groups()
        return 'deadlines', f"{yyyy}_{mm}_{dd}-{_sanitize_namestring(rest)}"
    m_doc = re.match(r"^(\d{4})_(\d{2})-([^/]+)$", stem)
    if m_doc:
        yyyy, mm, rest = m_doc.groups()
        return 'documents', f"{yyyy}_{mm}-{_sanitize_namestring(rest)}"
    return None, None


def organize_cmd(args: argparse.Namespace):
    """Organize files from sources into WKS folders based on naming rules.

    - YYYY_MM-name -> ~/Documents/YYYY_MM-name/
    - YYYY_MM_DD-name -> ~/deadlines/YYYY_MM_DD-name/
    Only acts on regular files. Non-matching files are skipped.
    """
    home = Path.home()
    sources = args.source or []
    if not sources:
        sources = [str(home/ 'Downloads'), str(home/ 'Desktop')]
    dry = not args.apply

    moves = []
    for src in sources:
        base = Path(src).expanduser()
        if not base.exists():
            continue
        for p in base.iterdir():
            try:
                if p.is_dir() or p.name.startswith('.'):
                    continue
                # Build folder name from the stem based on patterns
                kind, folder_name = _match_document_or_deadline_for_folder(p.stem)
                if not kind:
                    continue
                if kind == 'documents':
                    dest_dir = home / 'Documents' / folder_name
                else:
                    dest_dir = home / 'deadlines' / folder_name
                dest_dir.mkdir(parents=True, exist_ok=True)
                # Keep original filename in destination
                dest = dest_dir / p.name
                if dest.exists():
                    # Avoid overwriting
                    stem = p.stem
                    suffix = p.suffix
                    ts = datetime.now().strftime('%Y%m%d%H%M%S')
                    dest = dest_dir / f"{stem}-{ts}{suffix}"
                moves.append((p, dest))
            except Exception:
                continue

    # Optional repair step for previously-created folders that included extensions
    if args.repair:
        repaired = 0
        for root in [home / 'Documents', home / 'deadlines']:
            if not root.exists():
                continue
            for d in root.iterdir():
                if not d.is_dir():
                    continue
                name = d.name
                if '.' not in name:
                    continue
                # Only consider if it looks like a WKS-style folder name with a date prefix
                if re.match(r"^\d{4}_\d{2}(_\d{2})?-", name):
                    new_name = re.sub(r"\.[^.]+$", "", name)
                    if new_name == name:
                        continue
                    target = d.parent / new_name
                    if target.exists():
                        ts = datetime.now().strftime('%Y%m%d%H%M%S')
                        target = d.parent / f"{new_name}-{ts}"
                    print(("Would rename" if dry else "Renaming") + f" folder: {d} -> {target}")
                    if not dry:
                        try:
                            d.rename(target)
                            repaired += 1
                        except Exception as e:
                            print(f"  Failed to rename {d} -> {target}: {e}")
        if repaired:
            print(f"Repaired {repaired} folder name(s).")

    if not moves:
        print("No files matched YYYY_MM[-name] or YYYY_MM_DD[-name] patterns in sources.")
        return 0

    print(("Planned" if dry else "Applying") + f" {len(moves)} move(s):")
    for src, dest in moves:
        print(f"  {src} -> {dest}")

    if dry:
        print("\nRun again with --apply to perform these moves.")
        return 0

    # Apply
    for src, dest in moves:
        try:
            shutil.move(str(src), str(dest))
        except Exception as e:
            print(f"Failed: {src} -> {dest}: {e}")
    print("Done.")
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

    org = sub.add_parser("organize", help="Organize files by WKS rules from sources (Downloads/Desktop by default)")
    org.add_argument("--source", action="append", help="Source directory (repeatable). Defaults: ~/Downloads, ~/Desktop")
    org.add_argument("--apply", action="store_true", help="Apply changes (default is dry-run)")
    org.add_argument("--repair", action="store_true", help="Also repair folder names in ~/Documents and ~/deadlines (remove file extensions)")
    org.set_defaults(func=organize_cmd)

    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 2
    res = args.func(args)
    return 0 if res is None else res


if __name__ == "__main__":
    raise SystemExit(main())
