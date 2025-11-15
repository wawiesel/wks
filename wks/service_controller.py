"""
Service Controller - shared service/daemon status logic for CLI and MCP.

This module encapsulates all data gathering needed to report service status so
that both the CLI (`wks0 service status`) and the MCP server can reuse the same
implementation without duplicating code. Helper utilities around launchd
integration are also centralised here.
"""

from __future__ import annotations

import json
import os
import platform
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import mongoctl
from .config import load_config, mongo_settings
from .constants import WKS_HOME_EXT


LOCK_FILE = Path.home() / WKS_HOME_EXT / "daemon.lock"


def _fmt_bool(value: Optional[bool], color: bool = False) -> str:
    if value is None:
        return "-"
    if color:
        # Return Rich markup for coloring
        return "[green]true[/green]" if value else "[red]false[/red]"
    return "true" if value else "false"


def _format_timestamp_value(value: Optional[Any], fmt: str) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    from datetime import datetime

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


def _pid_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def stop_managed_mongo() -> None:
    mongoctl.stop_managed_mongo()


def agent_label() -> str:
    return "com.wieselquist.wks0"


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
    return mongo_settings(load_config())["uri"]


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
class ServiceStatusData:
    running: Optional[bool] = None
    uptime: Optional[str] = None
    pid: Optional[int] = None
    pending_deletes: Optional[int] = None
    pending_mods: Optional[int] = None
    ok: Optional[bool] = None
    lock: Optional[bool] = None
    last_error: Optional[str] = None
    fs_rate_short: Optional[float] = None
    fs_rate_long: Optional[float] = None
    fs_rate_weighted: Optional[float] = None
    launch: ServiceStatusLaunch = field(default_factory=ServiceStatusLaunch)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
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

    def _build_health_rows(self) -> List[Tuple[str, str]]:
        """Build Health section rows."""
        return [
            ("[bold cyan]Health[/bold cyan]", ""),
            ("  Running", _fmt_bool(self.running, color=True)),
            ("  Uptime", self.uptime or "-"),
            ("  PID", str(self.pid) if self.pid is not None else "-"),
            ("  OK", _fmt_bool(self.ok, color=True)),
            ("  Lock", _fmt_bool(self.lock, color=True)),
            (
                "  Type",
                self.launch.type
                if (self.launch and self.launch.present() and self.launch.type)
                else "LaunchAgent",
            ),
        ]

    def _build_filesystem_rows(self) -> List[Tuple[str, str]]:
        """Build File System section rows."""
        rows: List[Tuple[str, str]] = [("[bold cyan]File System[/bold cyan]", "")]
        rows.append(("  Pending deletes", str(self.pending_deletes) if self.pending_deletes is not None else "-"))
        rows.append(("  Pending mods", str(self.pending_mods) if self.pending_mods is not None else "-"))

        if self.fs_rate_weighted is not None:
            rows.append(("  Ops (last min)", str(int(self.fs_rate_weighted * 60))))
        if self.fs_rate_short is not None:
            rows.append(("  Ops/sec (10s)", f"{self.fs_rate_short:.2f}"))
        if self.fs_rate_long is not None:
            rows.append(("  Ops/sec (10m)", f"{self.fs_rate_long:.2f}"))
        if self.fs_rate_weighted is not None:
            rows.append(("  Ops/sec (weighted)", f"{self.fs_rate_weighted:.2f}"))

        return rows

    def _build_launch_rows(self) -> List[Tuple[str, str]]:
        """Build Launch section rows."""
        if not self.launch.present():
            return []

        return [
            ("[bold cyan]Launch[/bold cyan]", ""),
            ("  Program", self.launch.arguments or self.launch.program or "-"),
            ("  Stdout", self.launch.stdout or "-"),
            ("  Stderr", self.launch.stderr or "-"),
            ("  Path", self.launch.path or "-"),
            ("  Type", self.launch.type or "-"),
        ]

    def to_rows(self) -> List[Tuple[str, str]]:
        """Return rows grouped by section: Health, File System, Launch."""
        rows = []
        rows.extend(self._build_health_rows())
        rows.extend(self._build_filesystem_rows())
        return rows


class ServiceController:
    """Business logic for service status inspection."""

    @staticmethod
    def _read_launch_agent() -> Optional[ServiceStatusLaunch]:
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
            try:
                args_block = re.search(r"arguments = \{([^}]*)\}", launch_text, re.DOTALL)
                if args_block:
                    lines = [ln.strip() for ln in args_block.group(1).splitlines() if ln.strip()]
                    launch.arguments = " ".join(lines)
            except Exception:
                pass
            return launch
        except Exception:
            return None

    @staticmethod
    def _read_health(status: ServiceStatusData) -> None:
        health_path = Path.home() / WKS_HOME_EXT / "health.json"
        health: Dict[str, Any] = {}

        if health_path.exists():
            try:
                with open(health_path, "r") as f:
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
