import pytest

from tests.unit.conftest import create_tracked_wks_config, run_cmd
from wks.api.monitor import cmd_filter_add

pytestmark = pytest.mark.monitor


@pytest.mark.parametrize(
    ("overrides", "list_name", "value"),
    [
        ({}, "include_paths", "/tmp/x"),
        ({}, "include_dirnames", "testdir"),
        ({}, "include_globs", "*.py"),
    ],
)
def test_cmd_filter_add_success_cases(monkeypatch, overrides, list_name, value):
    """Requirements:
    - MON-001
    - MON-006"""
    cfg = create_tracked_wks_config(monkeypatch, overrides)

    result = run_cmd(cmd_filter_add.cmd_filter_add, list_name=list_name, value=value)

    assert result.output["success"] is True
    assert cfg.save_calls == 1


@pytest.mark.parametrize(
    ("overrides", "list_name", "value", "message"),
    [
        ({}, "unknown_list", "test", "Unknown list_name"),
        ({}, "include_dirnames", "   ", "cannot be empty"),
        ({}, "include_dirnames", "test*", "wildcard characters"),
        ({"filter": {"exclude_dirnames": ["testdir"]}}, "include_dirnames", "testdir", "already present"),
        ({}, "include_globs", "   ", "cannot be empty"),
        ({}, "include_dirnames", "invalid/path", "validation_failed"),
    ],
)
def test_cmd_filter_add_rejects_invalid_values(monkeypatch, overrides, list_name, value, message):
    """Requirements:
    - MON-001
    - MON-006"""
    cfg = create_tracked_wks_config(monkeypatch, overrides)

    result = run_cmd(cmd_filter_add.cmd_filter_add, list_name=list_name, value=value)

    assert result.output["success"] is False
    if message == "validation_failed":
        assert result.output["validation_failed"] is True
        assert cfg.save_calls == 0
        return
    output_text = f"{result.output.get('message', '')} {' '.join(result.output.get('errors', []))}"
    assert message in output_text or message in result.result
    assert cfg.save_calls == 0


@pytest.mark.parametrize(
    ("overrides", "list_name", "value"),
    [
        ({"filter": {"include_dirnames": ["testdir"]}}, "include_dirnames", "testdir"),
        ({"filter": {"include_globs": ["*.md"]}}, "include_globs", "*.md"),
    ],
)
def test_cmd_filter_add_duplicate_values(monkeypatch, overrides, list_name, value):
    """Requirements:
    - MON-001
    - MON-006"""
    cfg = create_tracked_wks_config(monkeypatch, overrides)

    result = run_cmd(cmd_filter_add.cmd_filter_add, list_name=list_name, value=value)

    assert result.output["success"] is False
    assert result.output["already_exists"] is True
    assert cfg.save_calls == 0


def test_cmd_filter_add_internal_error(monkeypatch):
    """Requirements:
    - MON-001
    - MON-006"""
    create_tracked_wks_config(monkeypatch)

    import wks.api.monitor.cmd_filter_add as filter_add_mod

    monkeypatch.setattr(filter_add_mod, "validate_value", lambda *args: (None, None))

    with pytest.raises(RuntimeError, match="value_to_store should not be None"):
        run_cmd(filter_add_mod.cmd_filter_add, list_name="include_paths", value="test")
