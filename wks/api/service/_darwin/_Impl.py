import os
import subprocess
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..ServiceStatus import ServiceStatus

from ...config.WKSConfig import WKSConfig
from .._AbstractImpl import _AbstractImpl
from .._shared import prepare_service_home, remove_daemon_lock, resolve_wksc_path
from ..ServiceConfig import ServiceConfig
from ._Data import _Data

if TYPE_CHECKING:
    from ..ServiceStatus import ServiceStatus


class _Impl(_AbstractImpl):
    @staticmethod
    def _get_launch_agents_dir() -> Path:
        return Path.home() / "Library" / "LaunchAgents"

    @staticmethod
    def _get_plist_path(label: str) -> Path:
        return _Impl._get_launch_agents_dir() / f"{label}.plist"

    @staticmethod
    def _create_plist_content(config: _Data, wksc_path: str, restrict_dir: Path | None = None) -> str:
        working_directory, log_file = prepare_service_home()

        program_args = f"""    <string>{wksc_path}</string>
    <string>daemon</string>
    <string>start</string>
    <string>--blocking</string>"""
        if restrict_dir is not None:
            from ....utils.normalize_path import normalize_path

            restrict_path = str(normalize_path(restrict_dir))
            program_args += f"""
    <string>--restrict</string>
    <string>{restrict_path}</string>"""

        wksc_dir = Path(wksc_path).parent
        import shutil

        mongod_path = shutil.which("mongod")
        mongod_dir = Path(mongod_path).parent if mongod_path else None

        path_str = f"{wksc_dir}:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
        if mongod_dir and str(mongod_dir) not in path_str:
            path_str = f"{mongod_dir}:{path_str}"

        plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>{config.label}</string>
  <key>LimitLoadToSessionType</key>
  <string>Aqua</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>{path_str}</string>
    <key>WKS_HOME</key>
    <string>{working_directory}</string>
  </dict>
  <key>ProgramArguments</key>
  <array>
{program_args}
  </array>
  <key>WorkingDirectory</key>
  <string>{working_directory}</string>
  <key>RunAtLoad</key>
  <{"true" if config.run_at_load else "false"}/>
  <key>KeepAlive</key>
  <{"true" if config.keep_alive else "false"}/>
  <key>StandardOutPath</key>
  <string>{log_file}</string>
  <key>StandardErrorPath</key>
  <string>{log_file}</string>
</dict>
</plist>"""
        return plist

    def __init__(self, service_config: ServiceConfig | None = None):
        if service_config is None:
            config = WKSConfig.load()
            service_config = config.service

        if not isinstance(service_config.data, _Data):
            raise ValueError("macOS service config data is required")
        self.config = service_config
        self._data: _Data = service_config.data

    def install_service(self, restrict_dir: Path | None = None) -> dict[str, Any]:
        wksc_path = resolve_wksc_path()

        plist_path = self._get_plist_path(self._data.label)
        plist_dir = plist_path.parent

        plist_dir.mkdir(parents=True, exist_ok=True)

        plist_content = self._create_plist_content(self._data, wksc_path, restrict_dir=restrict_dir)

        plist_path.write_text(plist_content, encoding="utf-8")

        uid = os.getuid()
        try:
            result = subprocess.run(
                ["launchctl", "print", f"gui/{uid}/{self._data.label}"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                raise RuntimeError("Service is already installed and loaded. Use 'wksc service uninstall' first.")
        except RuntimeError:
            raise  # Re-raise our error
        except Exception:
            pass  # If check fails, proceed with bootstrap

        try:
            subprocess.run(
                ["launchctl", "bootstrap", f"gui/{uid}", str(plist_path)],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to load launchd service: {e.stderr}") from e

        return {
            "success": True,
            "type": "darwin",
            "label": self._data.label,
            "plist_path": str(plist_path),
        }

    def uninstall_service(self) -> dict[str, Any]:
        plist_path = self._get_plist_path(self._data.label)

        if not plist_path.exists():
            return {
                "success": False,
                "type": "darwin",
                "label": self._data.label,
                "error": "Service is not installed (plist not found).",
            }

        uid = os.getuid()

        with suppress(Exception):
            subprocess.run(
                ["launchctl", "bootout", f"gui/{uid}", str(plist_path)],
                check=False,  # Don't fail if already unloaded
                capture_output=True,
                text=True,
            )

        if plist_path.exists():
            plist_path.unlink()

        remove_daemon_lock()

        return {
            "success": True,
            "type": "darwin",
            "label": self._data.label,
        }

    def get_service_status(self) -> "ServiceStatus":
        from ..ServiceStatus import ServiceStatus

        plist_path = self._get_plist_path(self._data.label)
        uid = os.getuid()

        status = ServiceStatus(
            installed=plist_path.exists(),
            unit_path=str(plist_path),
        )

        if status.installed:
            try:
                result = subprocess.run(
                    ["launchctl", "print", f"gui/{uid}/{self._data.label}"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if result.returncode == 0:
                    for line in result.stdout.splitlines():
                        if line.strip().startswith("pid ="):
                            with suppress(ValueError, IndexError):
                                status.pid = int(line.split("=", 1)[1].strip())
                                status.running = True
            except Exception:
                pass

        return status

    def start_service(self) -> dict[str, Any]:
        uid = os.getuid()
        plist_path = self._get_plist_path(self._data.label)

        def _running_result(action: str) -> dict[str, Any]:
            import time

            time.sleep(0.5)
            status = self.get_service_status()
            if status.pid:
                return {
                    "success": True,
                    "type": "darwin",
                    "label": self._data.label,
                    "action": action,
                    "pid": status.pid,
                }
            log_path = WKSConfig.get_home_dir() / "logs" / "service.log"
            return {
                "success": False,
                "error": f"Service failed to start (no PID found). Check logs at: {log_path}",
            }

        try:
            result = subprocess.run(
                ["launchctl", "print", f"gui/{uid}/{self._data.label}"],
                capture_output=True,
                text=True,
                check=False,
            )
            service_loaded = result.returncode == 0
        except Exception:
            service_loaded = False

        if not service_loaded and plist_path.exists():
            try:
                subprocess.run(
                    ["launchctl", "bootstrap", f"gui/{uid}", str(plist_path)],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                bootstrap_result = _running_result("bootstrapped")
                if bootstrap_result["success"]:
                    return bootstrap_result
                service_loaded = True
            except subprocess.CalledProcessError as e:
                status = self.get_service_status()
                if status.pid:
                    return {
                        "success": True,
                        "type": "darwin",
                        "label": self._data.label,
                        "action": "bootstrapped",
                        "pid": status.pid,
                        "note": "launchctl bootstrap reported an error, but the service is running.",
                    }
                if status.installed:
                    service_loaded = True
                else:
                    return {
                        "success": False,
                        "error": f"Failed to bootstrap service: {e.stderr}",
                    }

        if service_loaded:
            try:
                subprocess.run(
                    ["launchctl", "kickstart", "-k", f"gui/{uid}/{self._data.label}"],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                return _running_result("kickstarted")
            except subprocess.CalledProcessError as e:
                return {
                    "success": False,
                    "error": e.stderr,
                }
        return {
            "success": False,
            "error": "Service is not loaded and no plist was available to bootstrap.",
        }

    def stop_service(self) -> dict[str, Any]:
        uid = os.getuid()
        try:
            subprocess.run(
                ["launchctl", "bootout", f"gui/{uid}/{self._data.label}"],
                check=True,
                capture_output=True,
                text=True,
            )
            return {
                "success": True,
                "type": "darwin",
                "label": self._data.label,
            }
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else ""
            if "No such process" in error_msg or e.returncode == 3:
                return {
                    "success": True,
                    "type": "darwin",
                    "label": self._data.label,
                    "note": "Service was not running (already stopped).",
                }
            return {
                "success": False,
                "error": f"Failed to stop service: {error_msg}" if error_msg else "Failed to stop service.",
            }
