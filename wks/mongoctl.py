"""
Helpers for managing the local MongoDB process that backs wks0.

Shared across the CLI and daemon so launchd/autostart paths behave
the same as manual CLI invocations.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional

from pymongo.uri_parser import parse_uri as _parse_mongo_uri

import pymongo

from .utils import wks_home_path

MONGO_ROOT = wks_home_path("mongodb")
MONGO_PID_FILE = MONGO_ROOT / "mongod.pid"
MONGO_MANAGED_FLAG = MONGO_ROOT / "managed"
_LOCAL_URI_HOSTS = {"localhost", "127.0.0.1", "::1"}


def pid_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def mongo_ping(uri: str, timeout_ms: int = 500) -> bool:
    try:
        client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=timeout_ms, connectTimeoutMS=timeout_ms)
        client.admin.command("ping")
        return True
    except Exception:
        return False


def _local_node(uri: str) -> Optional[tuple[str, int]]:
    """Return the single loopback node defined by the URI, if any."""
    if not uri or uri.startswith("mongodb+srv://"):
        return None

    try:
        parsed = _parse_mongo_uri(uri, validate=False)
    except Exception:
        return None

    nodes = parsed.get("nodelist") or []
    if len(nodes) != 1:
        return None

    host, port = nodes[0]
    if host not in _LOCAL_URI_HOSTS:
        return None
    return host, port


def _is_local_uri(uri: str) -> bool:
    return _local_node(uri) is not None


def ensure_mongo_running(uri: str, *, record_start: bool = False) -> None:
    uri = (uri or "").strip()
    if not uri:
        print("Fatal: MongoDB URI is empty; configure db.uri in config.json")
        raise SystemExit(2)

    if mongo_ping(uri):
        return
    local_node = _local_node(uri)
    if local_node and shutil.which("mongod"):
        host, port = local_node
        bind_ip = "127.0.0.1" if host in ("localhost", "127.0.0.1") else host
        dbroot = MONGO_ROOT
        dbpath = dbroot / "db"
        logfile = dbroot / "mongod.log"
        dbroot.mkdir(parents=True, exist_ok=True)
        dbpath.mkdir(parents=True, exist_ok=True)
        pidfile = MONGO_PID_FILE if record_start else (dbroot / "mongod.pid.tmp")
        proc_pid: Optional[int] = None
        try:
            if pidfile.exists():
                pidfile.unlink()
        except Exception:
            pass
        try:
            with open(logfile, "ab") as log_handle:
                proc = subprocess.Popen(
                    [
                        "mongod",
                        "--dbpath",
                        str(dbpath),
                        "--logpath",
                        str(logfile),
                        "--logappend",
                        "--bind_ip",
                        bind_ip,
                        "--port",
                        str(port),
                    ],
                    stdout=log_handle,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
            proc_pid = proc.pid
            try:
                pidfile.write_text(str(proc_pid))
            except Exception:
                pass
        except Exception as exc:
            print(f"Fatal: failed to auto-start local mongod: {exc}")
            raise SystemExit(2)
        deadline = time.time() + 5.0
        while time.time() < deadline:
            if mongo_ping(uri, timeout_ms=1000):
                if record_start:
                    if proc_pid:
                        try:
                            MONGO_MANAGED_FLAG.write_text(str(proc_pid))
                        except Exception:
                            pass
                else:
                    try:
                        pidfile.unlink()
                    except Exception:
                        pass
                return
            time.sleep(0.3)
        print(f"Fatal: mongod started but MongoDB still unreachable; check logs in {dbroot}/mongod.log")
        if proc_pid:
            try:
                os.kill(proc_pid, signal.SIGTERM)
            except Exception:
                pass
        raise SystemExit(2)
    print(f"Fatal: MongoDB not reachable at {uri}; start mongod and retry.")
    raise SystemExit(2)


def stop_managed_mongo() -> None:
    if not MONGO_MANAGED_FLAG.exists() or not MONGO_PID_FILE.exists():
        return
    try:
        pid = int(MONGO_MANAGED_FLAG.read_text().strip())
    except Exception:
        pid = None
    try:
        if pid:
            os.kill(pid, signal.SIGTERM)
            for _ in range(20):
                if not pid_running(pid):
                    break
                time.sleep(0.1)
        MONGO_MANAGED_FLAG.unlink(missing_ok=True)
        MONGO_PID_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def create_client(
    uri: str,
    *,
    server_timeout: int = 500,
    connect_timeout: int = 500,
    ensure_running: bool = True,
):
    """Return a pymongo client, optionally ensuring the server is running."""
    if ensure_running:
        try:
            ensure_mongo_running(uri)
        except SystemExit:
            raise
        except Exception:
            pass
    return pymongo.MongoClient(
        uri,
        serverSelectionTimeoutMS=server_timeout,
        connectTimeoutMS=connect_timeout,
    )


class MongoGuard:
    """Background watcher that keeps the managed local MongoDB online."""

    def __init__(self, uri: str, *, ping_interval: float = 10.0):
        self.uri = (uri or "").strip()
        self.ping_interval = max(float(ping_interval), 0.01)
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._manage_local = _is_local_uri(self.uri)

    def start(self, *, record_start: bool = True) -> None:
        if not self.uri:
            return
        ensure_mongo_running(self.uri, record_start=record_start)
        if not self._manage_local:
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        thread = threading.Thread(target=self._loop, name="mongo-guard", daemon=True)
        self._thread = thread
        thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        thread = self._thread
        if not thread:
            return
        self._stop_event.set()
        try:
            thread.join(timeout)
        except Exception:
            pass
        self._thread = None
        self._stop_event = threading.Event()

    def is_running(self) -> bool:
        thread = self._thread
        return bool(thread and thread.is_alive())

    def _loop(self) -> None:
        while not self._stop_event.wait(self.ping_interval):
            if mongo_ping(self.uri, timeout_ms=1000):
                continue
            try:
                ensure_mongo_running(self.uri, record_start=True)
                print("Mongo guard: restarted local mongod after ping failure")
            except SystemExit:
                # Service startup already handles fatal exit; guard keeps trying
                continue
            except Exception:
                continue
