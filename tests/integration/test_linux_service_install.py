"""Integration test for Linux systemd service installation.

This test runs in a Docker container with systemd to verify that the Linux
service backend can actually install, start, stop, and uninstall systemd user services.

Requires Docker and a systemd-enabled container image.
"""

import subprocess
from pathlib import Path

import pytest

from wks.api.config.WKSConfig import WKSConfig
from wks.api.service.Service import Service


def _check_systemd_available() -> bool:
    """Check if systemd is available (running in Docker with systemd)."""
    try:
        result = subprocess.run(
            ["systemctl", "--user", "is-system-running"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        # systemd is available if command succeeds (even if system is not fully running)
        return result.returncode == 0 or "running" in result.stdout.lower()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


@pytest.mark.integration
@pytest.mark.linux_service
def test_linux_service_install_lifecycle(tmp_path, monkeypatch):
    """Test full lifecycle: install, start, status, stop, uninstall."""
    if not _check_systemd_available():
        pytest.skip("systemd not available (not running in Docker with systemd)")

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
            "database": "monitor",
            "sync": {
                "max_documents": 1000000,
                "min_priority": 0.0,
                "prune_interval_secs": 300.0,
            },
        },
        "database": {
            "type": "mongomock",
            "prefix": "wks",
            "data": {},
        },
        "service": {
            "type": "linux",
            "sync_interval_secs": 60.0,
            "data": {
                "unit_name": "wks-test-integration.service",
                "enabled": False,
            },
        },
        "daemon": {
            "sync_interval_secs": 0.1,
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
