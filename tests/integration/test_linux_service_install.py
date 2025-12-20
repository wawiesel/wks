"""Integration test for Linux systemd service installation.

This test runs in a Docker container with systemd to verify that the Linux
service backend can actually install, start, stop, and uninstall systemd user services.

Requires Docker and a systemd-enabled container image.
"""

import os
import platform
import subprocess
from pathlib import Path

import pytest

from wks.api.config.WKSConfig import WKSConfig
from wks.api.service.Service import Service


def _check_systemd_available() -> bool:
    """Check if systemd is available (running in Docker with systemd).

    This check verifies that systemd is running and user services are available.
    """
    try:
        # First check if systemctl exists
        result = subprocess.run(
            ["systemctl", "--version"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode != 0:
            return False

        # Check if systemd is running (PID 1 check)
        try:
            init_process = Path("/proc/1/comm").read_text().strip()
            if init_process != "systemd":
                return False
        except Exception:
            return False

        # Check if user systemd session is available
        # Use list-units as it's more reliable than is-system-running for user services
        result = subprocess.run(
            ["systemctl", "--user", "list-units", "--no-pager"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        # If we can list units, systemd user session is working
        # Check for common errors in stderr
        if result.stderr:
            error_lower = result.stderr.lower()
            if (
                "failed to connect" in error_lower
                or "no such file" in error_lower
                or "connection refused" in error_lower
            ):
                return False
        # Return true if command succeeded (even if no units listed)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


@pytest.mark.integration
@pytest.mark.linux_service
def test_linux_service_install_lifecycle(tmp_path, monkeypatch):
    """Test full lifecycle: install, start, status, stop, uninstall.

    This test REQUIRES systemd and must run on Linux (or in a Docker container with systemd enabled).
    On non-Linux platforms, this test is skipped (we test platform-specific code on the appropriate platform).
    """
    # Only run on Linux - test platform-specific code on the appropriate platform
    if platform.system() != "Linux":
        pytest.skip(f"Linux service tests only run on Linux (current platform: {platform.system()})")

    # On Linux, systemd must be available
    if not _check_systemd_available():
        pytest.fail(
            "systemd not available - this test requires systemd "
            "(run in Docker with systemd or on a Linux system with systemd)"
        )

    # Set up WKS_HOME
    wks_home = tmp_path / ".wks"
    wks_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    # Create minimal config with Linux service backend
    config_dict = {
        "monitor": {
            "filter": {
                "include_paths": [],
                "exclude_paths": [],
                "include_dirnames": [],
                "exclude_dirnames": [],
                "include_globs": [],
                "exclude_globs": [],
            },
            "priority": {
                "dirs": {},
                "weights": {
                    "depth_multiplier": 0.9,
                    "underscore_multiplier": 0.5,
                    "only_underscore_multiplier": 0.1,
                    "extension_weights": {},
                },
            },
            "max_documents": 1000000,
            "min_priority": 0.0,
            "remote": {
                "mappings": [],
            },
        },
        "vault": {
            "type": "obsidian",
            "base_dir": "~/_vault",
        },
        "database": {
            "type": "mongomock",
            "prefix": "wks",
            "data": {},
        },
        "service": {
            "type": "linux",
            "data": {
                "unit_name": "wks-test-integration.service",
                "enabled": False,
            },
        },
        "daemon": {
            "sync_interval_secs": 0.1,
        },
        "log": {
            "level": "INFO",
            "debug_retention_days": 0.5,
            "info_retention_days": 1.0,
            "warning_retention_days": 2.0,
            "error_retention_days": 7.0,
        },
    }

    config = WKSConfig.model_validate(config_dict)
    config.save()

    # Initialize service
    with Service(config.service) as service:
        # 1. Install service
        install_result = service.install_service()
        assert install_result["success"] is True
        assert install_result["type"] == "linux"
        assert install_result["unit_name"] == "wks-test-integration.service"
        assert Path(install_result["unit_path"]).exists()

        # 2. Check status (should be installed but not running)
        status = service.get_service_status()
        assert status["installed"] is True
        assert status.get("running", False) is False

        # 3. Start service
        start_result = service.start_service()
        if not start_result.get("success"):
            # Print detailed debug info
            error_msg = start_result.get("error", "Unknown error")
            print("\n=== SERVICE START FAILED ===")
            print(f"Error: {error_msg}")

            # Show the unit file contents
            unit_path = Path.home() / ".config" / "systemd" / "user" / "wks-test-integration.service"
            if unit_path.exists():
                print(f"\n=== Unit file ({unit_path}) ===")
                print(unit_path.read_text())

            # Show journalctl output
            import subprocess

            result = subprocess.run(
                ["journalctl", "--user", "-u", "wks-test-integration.service", "-n", "20", "--no-pager"],
                capture_output=True,
                text=True,
            )
            print("\n=== journalctl output ===")
            print(result.stdout or result.stderr)

            # Show systemctl status
            result = subprocess.run(
                ["systemctl", "--user", "status", "wks-test-integration.service"], capture_output=True, text=True
            )
            print("\n=== systemctl status ===")
            print(result.stdout or result.stderr)

            # Show the service log file
            log_path = wks_home / "logs" / "service.log"
            print(f"\n=== Service log ({log_path}) ===")
            if log_path.exists():
                print(log_path.read_text())
            else:
                print("Log file does not exist")

            # Show the internal daemon log file
            internal_log = wks_home / "logfile"
            print(f"\n=== Internal Daemon Log ({internal_log}) ===")
            if internal_log.exists():
                print(internal_log.read_text())
            else:
                print("Internal log file does not exist")

            # Try running wksc daemon start manually to see the error
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

        # 4. Check status (should be running)
        status = service.get_service_status()
        assert status["installed"] is True
        assert status.get("running", False) is True

        # 5. Stop service
        stop_result = service.stop_service()
        assert stop_result["success"] is True

        # 6. Check status (should be installed but not running)
        status = service.get_service_status()
        assert status["installed"] is True
        assert status.get("running", False) is False

        # 7. Uninstall service
        uninstall_result = service.uninstall_service()
        assert uninstall_result["success"] is True

        # 8. Check status (should not be installed)
        status = service.get_service_status()
        assert status["installed"] is False
