"""Unit tests for macOS service backend edge cases."""

import subprocess
from unittest.mock import MagicMock

from wks.api.service._darwin._Impl import _Impl
from wks.api.service.ServiceConfig import ServiceConfig
from wks.api.service.ServiceStatus import ServiceStatus


def test_start_service_bootstrap_error_but_service_running(monkeypatch):
    """Treat bootstrap I/O errors as success if launchd actually started the job."""
    config = ServiceConfig(
        type="darwin",
        data={"label": "com.test.wks", "keep_alive": True, "run_at_load": False},  # type: ignore[arg-type]
    )
    impl = _Impl(config)

    print_result = MagicMock(returncode=1)
    bootstrap_error = subprocess.CalledProcessError(
        5,
        ["launchctl", "bootstrap", "gui/123", "/tmp/com.test.wks.plist"],
        stderr="Bootstrap failed: 5: Input/output error",
    )

    def fake_run(cmd, capture_output, text, check):
        if cmd[:2] == ["launchctl", "print"]:
            return print_result
        if cmd[:2] == ["launchctl", "bootstrap"]:
            raise bootstrap_error
        raise AssertionError(f"Unexpected command: {cmd}")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(
        _Impl,
        "get_service_status",
        lambda self: ServiceStatus(installed=True, running=True, pid=4242, unit_path="/tmp/com.test.wks.plist"),
    )
    monkeypatch.setattr(_Impl, "_get_plist_path", staticmethod(lambda label: MagicMock(exists=lambda: True)))

    result = impl.start_service()

    assert result["success"] is True
    assert result["label"] == "com.test.wks"
    assert result["pid"] == 4242


def test_start_service_bootstrap_then_kickstart(monkeypatch):
    """Bootstrap should be followed by kickstart when the job is only loaded."""
    config = ServiceConfig(
        type="darwin",
        data={"label": "com.test.wks", "keep_alive": True, "run_at_load": False},  # type: ignore[arg-type]
    )
    impl = _Impl(config)
    calls: list[list[str]] = []
    status_sequence = iter(
        [
            ServiceStatus(installed=True, running=False, pid=None, unit_path="/tmp/com.test.wks.plist"),
            ServiceStatus(installed=True, running=True, pid=5252, unit_path="/tmp/com.test.wks.plist"),
        ]
    )

    def fake_run(cmd, capture_output, text, check):
        calls.append(cmd)
        if cmd[:2] == ["launchctl", "print"]:
            return MagicMock(returncode=1)
        if cmd[:2] == ["launchctl", "bootstrap"]:
            return MagicMock(returncode=0)
        if cmd[:2] == ["launchctl", "kickstart"]:
            return MagicMock(returncode=0)
        raise AssertionError(f"Unexpected command: {cmd}")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(_Impl, "get_service_status", lambda self: next(status_sequence))
    monkeypatch.setattr(_Impl, "_get_plist_path", staticmethod(lambda label: MagicMock(exists=lambda: True)))

    result = impl.start_service()

    assert result["success"] is True
    assert result["pid"] == 5252
    assert any(cmd[:2] == ["launchctl", "bootstrap"] for cmd in calls)
    assert any(cmd[:2] == ["launchctl", "kickstart"] for cmd in calls)
