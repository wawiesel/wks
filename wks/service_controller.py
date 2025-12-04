"""
Service Controller - shared service/daemon status logic for CLI and MCP.

This module encapsulates all data gathering needed to report service status so
that both the CLI (`wksc service status`) and the MCP server can reuse the same
implementation without duplicating code. Helper utilities around launchd
integration are also centralised here.
"""

from __future__ import annotations

import json
import os
import platform
import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# from . import mongoctl
from .config import WKSConfig
from .constants import WKS_HOME_EXT

LOCK_FILE = Path.home() / WKS_HOME_EXT / "daemon.lock"


def _pid_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def stop_managed_mongo() -> None:
    # mongoctl.stop_managed_mongo()
    pass


def agent_label() -> str:
    return "com.wieselquist.wksc"


def agent_plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{agent_label()}.plist"


def is_macos() -> bool:
    return platform.system() == "Darwin"


def _launchctl(*args: str) -> int:
    try:
        return subprocess.call(["launchctl", *args], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        return 2


def agent_installed() -> bool:
    return agent_plist_path().exists()


def daemon_start_launchd() -> None:
    uid = os.getuid()
    pl = str(agent_plist_path())
    rc = _launchctl("kickstart", "-k", f"gui/{uid}/{agent_label()}")
    if rc == 0:
        return
    _launchctl("bootout", f"gui/{uid}", pl)
    _launchctl("bootstrap", f"gui/{uid}", pl)
    _launchctl("enable", f"gui/{uid}/{agent_label()}")
    _launchctl("kickstart", "-k", f"gui/{uid}/{agent_label()}")


def daemon_stop_launchd() -> None:
    uid = os.getuid()
    _launchctl("bootout", f"gui/{uid}", str(agent_plist_path()))


def daemon_status_launchd() -> int:
    uid = os.getuid()
    try:
        return subprocess.call(["launchctl", "print", f"gui/{uid}/{agent_label()}"])
    except Exception:
        return 3


def default_mongo_uri() -> str:
    try:
        config = WKSConfig.load()
        return config.mongo.uri
    except Exception:
        # Fallback for very old configs or bootstrap issues
        return "mongodb://localhost:27017"


@dataclass
class ServiceStatusLaunch:
    state: str | None = None
    active_count: str | None = None
    pid: str | None = None
    program: str | None = None
    arguments: str | None = None
    working_dir: str | None = None
    stdout: str | None = None
    stderr: str | None = None
    runs: str | None = None
    last_exit: str | None = None
    path: str | None = None
    type: str | None = None

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

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ServiceStatusData:
    running: bool | None = None
    uptime: str | None = None
    pid: int | None = None
    pending_deletes: int | None = None
    pending_mods: int | None = None
    ok: bool | None = None
    lock: bool | None = None
    last_error: str | None = None
    fs_rate_short: float | None = None
    fs_rate_long: float | None = None
    fs_rate_weighted: float | None = None
    launch: ServiceStatusLaunch = field(default_factory=ServiceStatusLaunch)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "service": {
                "running": self.running,
                "uptime": self.uptime,
                "pid": self.pid,
                "pending_deletes": self.pending_deletes,
                "pending_mods": self.pending_mods,
                "ok": self.ok,
                "lock": self.lock,
                "last_error": self.last_error,
                "fs_rate_short": self.fs_rate_short,
                "fs_rate_long": self.fs_rate_long,
                "fs_rate_weighted": self.fs_rate_weighted,
            },
            "launch_agent": self.launch.as_dict(),
            "notes": list(self.notes),
        }


class ServiceController:
    """Business logic for service status inspection."""

    @staticmethod
    def _read_launch_agent() -> ServiceStatusLaunch | None:
        if not (is_macos() and agent_installed()):
            return None
        try:
            uid = os.getuid()
            out = subprocess.check_output(
                ["launchctl", "print", f"gui/{uid}/{agent_label()}"],
                stderr=subprocess.STDOUT,
            )
            launch_text = out.decode("utf-8", errors="ignore")

            def _find(pattern: str, default: str = "") -> str:
                match = re.search(pattern, launch_text)
                return match.group(1).strip() if match else default

            launch = ServiceStatusLaunch(
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
            # Parse arguments block if present
            args_block = re.search(r"arguments = \{([^}]*)\}", launch_text, re.DOTALL)
            if args_block:
                lines = [ln.strip() for ln in args_block.group(1).splitlines() if ln.strip()]
                launch.arguments = " ".join(lines)
            return launch
        except Exception:
            return None

    @staticmethod
    def _read_health(status: ServiceStatusData) -> None:
        health_path = Path.home() / WKS_HOME_EXT / "health.json"
        health: dict[str, Any] = {}

        if health_path.exists():
            try:
                with health_path.open() as f:
                    health = json.load(f)
            except Exception:
                status.notes.append("Failed to read health metrics")

        if health:
            status.running = bool(health.get("lock_present"))
            status.uptime = str(health.get("uptime_hms") or "")
            try:
                status.pid = int(health.get("pid"))
            except (ValueError, TypeError):
                status.pid = None
            status.pending_deletes = health.get("pending_deletes")
            status.pending_mods = health.get("pending_mods")
            status.ok = not bool(health.get("last_error"))
            status.lock = bool(health.get("lock_present"))
            if health.get("last_error"):
                status.last_error = str(health.get("last_error"))

            for attr, key in [
                ("fs_rate_short", "fs_rate_short"),
                ("fs_rate_long", "fs_rate_long"),
                ("fs_rate_weighted", "fs_rate_weighted"),
            ]:
                val = health.get(key)
                try:
                    setattr(status, attr, float(val) if val is not None else None)
                except (ValueError, TypeError):
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
                if not status.notes:
                    status.notes.append("WKS daemon: not running")

    @staticmethod
    def get_status() -> ServiceStatusData:
        status = ServiceStatusData()

        launch_info = ServiceController._read_launch_agent()
        if launch_info:
            status.launch = launch_info
        else:
            if is_macos() and agent_installed():
                status.notes.append("Launch agent status unavailable")

        ServiceController._read_health(status)

        return status


__all__ = [
    "LOCK_FILE",
    "ServiceController",
    "ServiceStatusData",
    "ServiceStatusLaunch",
    "_pid_running",
    "agent_installed",
    "agent_label",
    "agent_plist_path",
    "daemon_start_launchd",
    "daemon_status_launchd",
    "daemon_stop_launchd",
    "default_mongo_uri",
    "is_macos",
    "stop_managed_mongo",
]
