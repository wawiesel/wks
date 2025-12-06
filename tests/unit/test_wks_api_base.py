"""Unit tests for wks.api.base module."""

from unittest.mock import MagicMock, patch

import typer

from wks.api import base as api_base


def test_stage_result_success_inferred():
    """Test that StageResult infers success from output."""
    result = api_base.StageResult(announce="a", result="r", output={"success": False})
    assert result.success is False
    assert result.output["success"] is False


def test_inject_config_injects(monkeypatch):
    """Test that inject_config decorator injects config."""

    cfg = object()

    @api_base.inject_config
    def fn(config):
        return config

    monkeypatch.setattr("wks.api.base.WKSConfig.load", lambda: cfg)
    assert fn() is cfg


def test_get_typer_command_schema_skips_config_and_marks_required():
    """Test that get_typer_command_schema skips config and marks required params."""
    app = typer.Typer()

    def sample(config, path: str, optional: int = 3):  # type: ignore[unused-argument]
        return path, optional

    app.command(name="sample")(sample)

    schema = api_base.get_typer_command_schema(app, "sample")
    assert "config" not in schema["properties"]
    assert "path" in schema["required"]
    assert "optional" not in (schema["required"] or [])


def test_handle_stage_result_live_mode():
    """Test that handle_stage_result triggers live mode when live_interval is set."""
    # Create a simple command function
    def cmd_test() -> api_base.StageResult:
        return api_base.StageResult(
            announce="Testing",
            result="Done",
            output={"test": True},
            success=True,
        )

    # Mock Typer context with live_interval
    mock_ctx = MagicMock()
    mock_ctx.meta = {"live_interval": 1.0, "display_format": "yaml"}
    mock_ctx.parent = None  # No parent context

    wrapped = api_base.handle_stage_result(cmd_test)

    with patch("wks.api.base.typer.get_current_context", return_value=mock_ctx):
        with patch("wks.api.base.get_display") as mock_get_display:
            with patch("wks.api.base._run_live_mode") as mock_live:
                with patch("wks.api.base._run_single_execution") as mock_single:
                    mock_display = MagicMock()
                    mock_get_display.return_value = mock_display
                    mock_live.side_effect = SystemExit(0)

                    try:
                        wrapped()
                    except SystemExit:
                        pass

                    # Verify live mode was called, single execution was not
                    mock_live.assert_called_once()
                    mock_single.assert_not_called()

                    # Verify live mode was called with correct interval
                    call_args = mock_live.call_args
                    assert call_args[0][4] == 1.0  # interval parameter


def test_handle_stage_result_no_live_mode():
    """Test that handle_stage_result uses single execution when live_interval is not set."""
    def cmd_test() -> api_base.StageResult:
        return api_base.StageResult(
            announce="Testing",
            result="Done",
            output={"test": True},
            success=True,
        )

    # Mock Typer context without live_interval
    mock_ctx = MagicMock()
    mock_ctx.meta = {"display_format": "yaml"}
    mock_ctx.parent = None

    wrapped = api_base.handle_stage_result(cmd_test)

    with patch("wks.api.base.typer.get_current_context", return_value=mock_ctx):
        with patch("wks.api.base.get_display") as mock_get_display:
            with patch("wks.api.base._run_live_mode") as mock_live:
                with patch("wks.api.base._run_single_execution") as mock_single:
                    mock_display = MagicMock()
                    mock_get_display.return_value = mock_display
                    mock_single.side_effect = SystemExit(0)

                    try:
                        wrapped()
                    except SystemExit:
                        pass

                    # Verify single execution was called, live mode was not
                    mock_single.assert_called_once()
                    mock_live.assert_not_called()


def test_handle_stage_result_live_mode_parent_context():
    """Test that handle_stage_result finds live_interval in parent context."""
    def cmd_test() -> api_base.StageResult:
        return api_base.StageResult(
            announce="Testing",
            result="Done",
            output={"test": True},
            success=True,
        )

    # Mock child context (no meta)
    mock_child_ctx = MagicMock()
    mock_child_ctx.meta = {"display_format": "yaml"}

    # Mock parent context (has live_interval)
    mock_parent_ctx = MagicMock()
    mock_parent_ctx.meta = {"live_interval": 2.0, "display_format": "yaml"}
    mock_parent_ctx.parent = None

    # Link contexts
    mock_child_ctx.parent = mock_parent_ctx

    wrapped = api_base.handle_stage_result(cmd_test)

    with patch("wks.api.base.typer.get_current_context", return_value=mock_child_ctx):
        with patch("wks.api.base.get_display") as mock_get_display:
            with patch("wks.api.base._run_live_mode") as mock_live:
                with patch("wks.api.base._run_single_execution") as mock_single:
                    mock_display = MagicMock()
                    mock_get_display.return_value = mock_display
                    mock_live.side_effect = SystemExit(0)

                    try:
                        wrapped()
                    except SystemExit:
                        pass

                    # Verify live mode was called with parent's interval
                    mock_live.assert_called_once()
                    call_args = mock_live.call_args
                    assert call_args[0][4] == 2.0  # interval from parent
                    mock_single.assert_not_called()
