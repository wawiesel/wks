"""Service management commands (daemon start/stop/status/install/uninstall)."""

import argparse
import os
import platform
import signal
import subprocess
import sys
import time
from pathlib import Path

from ...constants import WKS_HOME_EXT
from ...display.context import get_display
from ...service_controller import (
    LOCK_FILE,
    ServiceController,
    ServiceStatusData,
    agent_installed,
    daemon_start_launchd,
    daemon_status_launchd,
    daemon_stop_launchd,
    default_mongo_uri,
    is_macos,
    stop_managed_mongo,
)
from ..display_strategies import get_display_strategy
from ..helpers import maybe_write_json
# from ... import mongoctl
from ...mcp_setup import install_mcp_configs


# Launchd helpers
def _agent_label() -> str:
    """Unique launchd label bound to the new CLI name."""
    return "com.wieselquist.wks0"


def _agent_plist_path() -> Path:
    """Path to launchd plist file."""
    return Path.home() / "Library" / "LaunchAgents" / f"{_agent_label()}.plist"


def _launchctl_quiet(*args: str) -> int:
    """Run launchctl command quietly."""
    try:
        return subprocess.call(["launchctl", *args], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        print("launchctl not found; macOS only")
        return 2


def _plist_path() -> Path:
    """Path to plist file (alias for _agent_plist_path for compatibility)."""
    return _agent_plist_path()


# Service command implementations
def daemon_status(args: argparse.Namespace) -> int:
    """Show daemon status using appropriate display strategy."""
    try:
        strategy = get_display_strategy(args)
    except ValueError as e:
        return 2

    # Live mode requires CLI display
    if getattr(args, "live", False):
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
    maybe_write_json(args, payload)

    return strategy.render(status, args)


def _ensure_mcp_registration() -> None:
    try:
        install_mcp_configs()
    except Exception:
        pass


def daemon_start(_: argparse.Namespace):
    """Start daemon in background or via launchd if installed."""
    _ensure_mcp_registration()
    # mongoctl.ensure_mongo_running(default_mongo_uri(), record_start=True)
    if is_macos() and agent_installed():
        daemon_start_launchd()
        return
    # Start as background process: python -m wks.daemon
    env = os.environ.copy()
    python = sys.executable
    log_dir = Path.home() / WKS_HOME_EXT
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "daemon.log"
    # Prefer running against the local source tree when available
    try:
        proj_root = Path(__file__).resolve().parents[2]
        env["PYTHONPATH"] = f"{proj_root}:{env.get('PYTHONPATH', '')}"
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
    """Core daemon stop logic."""
    if is_macos() and agent_installed():
        daemon_stop_launchd()
        if stop_mongo:
            stop_managed_mongo()
        return
    if not LOCK_FILE.exists():
        print("WKS daemon is not running")
        if stop_mongo:
            stop_managed_mongo()
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
            stop_managed_mongo()


def daemon_stop(_: argparse.Namespace):
    """Stop daemon."""
    _daemon_stop_core(stop_mongo=True)


def daemon_restart(args: argparse.Namespace):
    """Restart daemon."""
    _ensure_mcp_registration()
    # macOS launchd-managed restart
    if is_macos() and agent_installed():
        try:
            # mongoctl.ensure_mongo_running(default_mongo_uri(), record_start=True)
            pass
        except Exception:
            pass
        try:
            daemon_stop_launchd()
        except Exception:
            pass
        time.sleep(0.5)
        daemon_start_launchd()
        return

    # Fallback: stop/start without touching databases
    try:
        _daemon_stop_core(stop_mongo=False)
    except Exception:
        pass
    time.sleep(0.5)
    try:
        # mongoctl.ensure_mongo_running(default_mongo_uri(), record_start=True)
        pass
    except Exception:
        pass
    daemon_start(args)


def daemon_install(args: argparse.Namespace):
    """Install launchd agent (macOS)."""
    if platform.system() != "Darwin":
        print("install is macOS-only (launchd)")
        return
    _ensure_mcp_registration()
    pl = _plist_path()
    pl.parent.mkdir(parents=True, exist_ok=True)
    log_dir = Path.home() / WKS_HOME_EXT
    log_dir.mkdir(exist_ok=True)
    # Use the current interpreter (works for system Python, venv, and pipx)
    python = sys.executable
    proj_root = Path(__file__).resolve().parents[2]
    xml = f"""
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.wieselquist.wks0</string>
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
    from ..helpers import make_progress
    with make_progress(total=6, display=args.display) as prog:
        prog.update("ensure mongo")
        # mongoctl.ensure_mongo_running(default_mongo_uri(), record_start=True)
        prog.update("bootout legacy")
        # Only bootout immediate predecessor if it exists
        old_plist = Path.home() / "Library" / "LaunchAgents" / "com.wieselquist.wkso.plist"
        if old_plist.exists():
            _launchctl_quiet("bootout", f"gui/{uid}", str(old_plist))
        prog.update("bootstrap")
        _launchctl_quiet("bootstrap", f"gui/{uid}", str(pl))
        prog.update("enable")
        _launchctl_quiet("enable", f"gui/{uid}/com.wieselquist.wks0")
        prog.update("kickstart")
        _launchctl_quiet("kickstart", "-k", f"gui/{uid}/com.wieselquist.wks0")
        prog.update("done")
    print(f"Installed and started: {pl}")


def daemon_uninstall(args: argparse.Namespace):
    """Uninstall launchd agent (macOS)."""
    if platform.system() != "Darwin":
        print("uninstall is macOS-only (launchd)")
        return
    pl = _plist_path()
    uid = os.getuid()
    from ..helpers import make_progress
    # Only clean up current label and immediate predecessor
    labels_to_remove = [
        "com.wieselquist.wks0",  # Current
        "com.wieselquist.wkso",  # Immediate predecessor
    ]
    with make_progress(total=len(labels_to_remove) * 2, display=args.display) as prog:
        for label in labels_to_remove:
            plist_path = Path.home() / "Library" / "LaunchAgents" / (label + ".plist")
            prog.update(f"bootout {label}")
            _launchctl_quiet("bootout", f"gui/{uid}", str(plist_path))
            prog.update(f"remove {label}.plist")
            if plist_path.exists():
                plist_path.unlink()
    stop_managed_mongo()
    print("Uninstalled.")


def _stop_service_for_reset(args: argparse.Namespace) -> None:
    """Stop current service agent."""
    try:
        if platform.system() == "Darwin":
            _launchctl_quiet("bootout", f"gui/{os.getuid()}", str(_plist_path()))
        else:
            daemon_stop(args)
    except Exception:
        pass


def _clear_local_agent_state() -> None:
    """Clear local agent state files."""
    try:
        home = Path.home()
        for name in [
            'file_ops.jsonl', 'monitor_state.json', 'activity_state.json', 'health.json',
            'daemon.lock', 'daemon.log', 'daemon.error.log'
        ]:
            p = home / WKS_HOME_EXT / name
            try:
                if p.exists():
                    p.unlink()
            except Exception:
                pass
    except Exception:
        pass


def _start_service_for_reset(args: argparse.Namespace) -> None:
    """Start service again after reset."""
    try:
        if platform.system() == "Darwin":
            pl = _plist_path()
            _launchctl_quiet("bootstrap", f"gui/{os.getuid()}", str(pl))
            _launchctl_quiet("enable", f"gui/{os.getuid()}/com.wieselquist.wks0")
            _launchctl_quiet("kickstart", "-k", f"gui/{os.getuid()}/com.wieselquist.wks0")
        else:
            daemon_start(args)
    except Exception:
        pass


def service_reset(args: argparse.Namespace) -> int:
    """Reset service: stop, clear state, restart."""
    _stop_service_for_reset(args)
    stop_managed_mongo()

    try:
        # mongoctl.ensure_mongo_running(default_mongo_uri(), record_start=True)
        pass
    except SystemExit:
        return 2

    _clear_local_agent_state()
    _start_service_for_reset(args)

    try:
        daemon_status(args)
    except Exception:
        pass

    return 0


def setup_service_parser(subparsers) -> None:
    """Setup service command parser."""
    svc = subparsers.add_parser("service", help="Install/start/stop the WKS daemon (macOS)")
    svcsub = svc.add_subparsers(dest="svc_cmd")

    def _svc_help(args, parser=svc):
        parser.print_help()
        return 2

    svc.set_defaults(func=_svc_help)

    svcinst = svcsub.add_parser("install", help="Install launchd agent (macOS)")
    svcinst.set_defaults(func=daemon_install)

    svcrem = svcsub.add_parser("uninstall", help="Uninstall launchd agent (macOS)")
    svcrem.set_defaults(func=daemon_uninstall)

    svcstart = svcsub.add_parser("start", help="Start daemon in background or via launchd if installed")
    svcstart.set_defaults(func=daemon_start)

    svcstop = svcsub.add_parser("stop", help="Stop daemon")
    svcstop.set_defaults(func=daemon_stop)

    svcstatus = svcsub.add_parser("status", help="Daemon status")
    svcstatus.add_argument(
        "--live",
        action="store_true",
        help="Keep display updated automatically (refreshes every 2 seconds)"
    )
    svcstatus.set_defaults(func=daemon_status)

    svcrestart = svcsub.add_parser("restart", help="Restart daemon")
    svcrestart.set_defaults(func=daemon_restart)

    svcreset = svcsub.add_parser("reset", help="Stop service, reset databases/state, and start service cleanly")
    svcreset.set_defaults(func=service_reset)
