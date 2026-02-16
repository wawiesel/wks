"""Unit tests for the top-level wks.api.cmd_status module."""

from collections.abc import Iterator

from tests.unit.conftest import run_cmd
from wks.api.cmd_status import cmd_status
from wks.api.config.StageResult import StageResult


def _fake_service_status() -> StageResult:
    def do_work(r: StageResult) -> Iterator[tuple[float, str]]:
        r.output = {"running": True, "pid": 1234, "installed": True}
        r.result = "ok"
        r.success = True
        yield (1.0, "done")

    return StageResult(announce="svc", progress_callback=do_work)


def _fake_log_status() -> StageResult:
    def do_work(r: StageResult) -> Iterator[tuple[float, str]]:
        r.output = {"entry_counts": {"debug": 5, "info": 10, "warn": 1, "error": 2}}
        r.result = "ok"
        r.success = True
        yield (1.0, "done")

    return StageResult(announce="log", progress_callback=do_work)


def _fake_monitor_status() -> StageResult:
    def do_work(r: StageResult) -> Iterator[tuple[float, str]]:
        r.output = {"tracked_files": 42, "last_sync": "2026-01-01T00:00:00"}
        r.result = "ok"
        r.success = True
        yield (1.0, "done")

    return StageResult(announce="mon", progress_callback=do_work)


def _fake_link_status() -> StageResult:
    def do_work(r: StageResult) -> Iterator[tuple[float, str]]:
        r.output = {"total_links": 100, "total_files": 50}
        r.result = "ok"
        r.success = True
        yield (1.0, "done")

    return StageResult(announce="link", progress_callback=do_work)


def _fake_vault_status() -> StageResult:
    def do_work(r: StageResult) -> Iterator[tuple[float, str]]:
        r.output = {"total_links": 200}
        r.result = "ok"
        r.success = True
        yield (1.0, "done")

    return StageResult(announce="vault", progress_callback=do_work)


def test_cmd_status_aggregates_all_sections(monkeypatch):
    """cmd_status returns output with all five subsystem sections."""
    import wks.api.link.cmd_status as link_mod
    import wks.api.log.cmd_status as log_mod
    import wks.api.monitor.cmd_status as mon_mod
    import wks.api.service.cmd_status as svc_mod
    import wks.api.vault.cmd_status as vault_mod

    monkeypatch.setattr(svc_mod, "cmd_status", _fake_service_status)
    monkeypatch.setattr(log_mod, "cmd_status", _fake_log_status)
    monkeypatch.setattr(mon_mod, "cmd_status", _fake_monitor_status)
    monkeypatch.setattr(link_mod, "cmd_status", _fake_link_status)
    monkeypatch.setattr(vault_mod, "cmd_status", _fake_vault_status)

    result = run_cmd(cmd_status)

    assert result.success is True
    assert "service" in result.output
    assert "log" in result.output
    assert "monitor" in result.output
    assert "link" in result.output
    assert "vault" in result.output

    assert result.output["service"]["running"] is True
    assert result.output["service"]["pid"] == 1234
    assert result.output["log"]["entry_counts"]["error"] == 2
    assert result.output["monitor"]["tracked_files"] == 42
    assert result.output["link"]["total_links"] == 100
    assert result.output["vault"]["total_links"] == 200


def test_cmd_status_handles_subsystem_failure(monkeypatch):
    """cmd_status captures errors from failing subsystems."""
    import wks.api.link.cmd_status as link_mod
    import wks.api.log.cmd_status as log_mod
    import wks.api.monitor.cmd_status as mon_mod
    import wks.api.service.cmd_status as svc_mod
    import wks.api.vault.cmd_status as vault_mod

    def _failing_status():
        raise RuntimeError("connection refused")

    monkeypatch.setattr(svc_mod, "cmd_status", _failing_status)
    monkeypatch.setattr(log_mod, "cmd_status", _fake_log_status)
    monkeypatch.setattr(mon_mod, "cmd_status", _fake_monitor_status)
    monkeypatch.setattr(link_mod, "cmd_status", _fake_link_status)
    monkeypatch.setattr(vault_mod, "cmd_status", _fake_vault_status)

    result = run_cmd(cmd_status)

    assert result.success is True
    assert "error" in result.output["service"]
    assert "connection refused" in result.output["service"]["error"]
    # Other sections should still succeed
    assert result.output["log"]["entry_counts"]["error"] == 2
