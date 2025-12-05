"""Unit tests for wks.api.monitor.app module."""

import pytest

from wks.api import base as api_base
from wks.api.monitor import app

pytestmark = pytest.mark.monitor


def test_monitor_app_wrapper_non_cli(monkeypatch):
    calls = []

    def progress_cb(callback):
        callback("step", 1.0)
        calls.append("progress")

    stage = api_base.StageResult(
        announce="a",
        result="done",
        output={"success": True, "payload": 1},
        progress_callback=progress_cb,
        progress_total=2,
    )

    from wks.api.base import handle_stage_result
    import pytest

    wrapped = handle_stage_result(lambda: stage)
    # handle_stage_result calls sys.exit() for CLI, so we need to catch SystemExit
    with pytest.raises(SystemExit) as exc_info:
        result = wrapped()
        assert result.output["payload"] == 1
    # Verify exit code is 0 for success
    assert exc_info.value.code == 0
    assert calls == ["progress"]
