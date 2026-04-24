import os
import platform
import subprocess
from pathlib import Path

import pytest

from tests.conftest import build_service_test_config
from wks.api.service.Service import Service


def _check_systemd_available() -> bool:
    try:
        result = subprocess.run(
            ["systemctl", "--version"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode != 0:
            return False

        try:
            init_process = Path("/proc/1/comm").read_text().strip()
            if init_process != "systemd":
                return False
        except Exception:
            return False

        result = subprocess.run(
            ["systemctl", "--user", "list-units", "--no-pager"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.stderr:
            error_lower = result.stderr.lower()
            if (
                "failed to connect" in error_lower
                or "no such file" in error_lower
                or "connection refused" in error_lower
            ):
                return False
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


@pytest.mark.integration
@pytest.mark.linux_service
def test_linux_service_install_lifecycle(tmp_path, monkeypatch):
    if platform.system() != "Linux":
        pytest.skip(f"Linux service tests only run on Linux (current platform: {platform.system()})")

    if not _check_systemd_available():
        pytest.fail(
            "systemd not available - this test requires systemd "
            "(run in Docker with systemd or on a Linux system with systemd)"
        )

    wks_home = tmp_path / ".wks"
    wks_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    config = build_service_test_config(
        tmp_path,
        service_type="linux",
        service_data={"unit_name": "wks-test-integration.service", "enabled": False},
    )
    config.save()

    with Service(config.service) as service:
        install_result = service.install_service()
        assert install_result["success"] is True
        assert install_result["type"] == "linux"
        assert install_result["unit_name"] == "wks-test-integration.service"
        assert Path(install_result["unit_path"]).exists()

        status = service.get_service_status()
        assert status.installed is True
        assert status.running is False

        start_result = service.start_service()
        if not start_result.get("success"):
            error_msg = start_result.get("error", "Unknown error")
            print("\n=== SERVICE START FAILED ===")
            print(f"Error: {error_msg}")

            unit_path = Path.home() / ".config" / "systemd" / "user" / "wks-test-integration.service"
            if unit_path.exists():
                print(f"\n=== Unit file ({unit_path}) ===")
                print(unit_path.read_text())

            import subprocess

            result = subprocess.run(
                ["journalctl", "--user", "-u", "wks-test-integration.service", "-n", "20", "--no-pager"],
                capture_output=True,
                text=True,
            )
            print("\n=== journalctl output ===")
            print(result.stdout or result.stderr)

            result = subprocess.run(
                ["systemctl", "--user", "status", "wks-test-integration.service"], capture_output=True, text=True
            )
            print("\n=== systemctl status ===")
            print(result.stdout or result.stderr)

            log_path = wks_home / "logs" / "service.log"
            print(f"\n=== Service log ({log_path}) ===")
            if log_path.exists():
                print(log_path.read_text())
            else:
                print("Log file does not exist")

            internal_log = wks_home / "logfile"
            print(f"\n=== Internal Daemon Log ({internal_log}) ===")
            if internal_log.exists():
                print(internal_log.read_text())
            else:
                print("Internal log file does not exist")

            print("\n=== Manual wksc daemon start test ===")
            result = subprocess.run(
                ["wksc", "daemon", "start"],
                capture_output=True,
                text=True,
                env={**os.environ, "WKS_HOME": str(wks_home)},
            )
            print(f"stdout: {result.stdout}")
            print(f"stderr: {result.stderr}")
            print(f"returncode: {result.returncode}")

            pytest.fail(f"Service start failed: {error_msg}")
        assert start_result["success"] is True

        status = service.get_service_status()
        assert status.installed is True
        assert status.running is True

        stop_result = service.stop_service()
        assert stop_result["success"] is True

        status = service.get_service_status()
        assert status.installed is True
        assert status.running is False

        uninstall_result = service.uninstall_service()
        assert uninstall_result["success"] is True

        status = service.get_service_status()
        assert status.installed is False
