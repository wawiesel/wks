"""Unit tests for wks.api.monitor.app module."""

from unittest.mock import MagicMock, patch

import pytest
import typer

from wks.api import base as api_base
from wks.api.monitor.app import (
    check_command,
    filter_add_command,
    filter_remove_command,
    filter_show_command,
    monitor_app,
    monitor_callback,
    priority_add_command,
    priority_remove_command,
    sync_command,
)

pytestmark = pytest.mark.monitor


class TestMonitorApp:
    """Test monitor_app Typer app."""

    def test_monitor_app_is_typer(self):
        """Test monitor_app is a Typer instance."""
        assert isinstance(monitor_app, typer.Typer)
        assert monitor_app.info.name == "monitor"

    def test_monitor_callback_without_subcommand(self):
        """Test monitor_callback shows help when no subcommand."""
        ctx = MagicMock()
        ctx.invoked_subcommand = None
        ctx.get_help.return_value = "help text"

        with patch("wks.api.monitor.app.typer.echo") as mock_echo:
            with patch("wks.api.monitor.app.typer.Exit", side_effect=SystemExit) as mock_exit:
                with pytest.raises(SystemExit):
                    monitor_callback(ctx)
                mock_echo.assert_called_once_with("help text", err=True)
                mock_exit.assert_called_once()

    def test_monitor_callback_with_subcommand(self):
        """Test monitor_callback does nothing when subcommand exists."""
        ctx = MagicMock()
        ctx.invoked_subcommand = "status"

        # Should not raise
        monitor_callback(ctx)


class TestCheckCommand:
    """Test check_command wrapper function."""

    def test_check_command_with_path(self):
        """Test check_command calls wrapped function when path provided."""
        ctx = MagicMock()

        with patch("wks.api.monitor.app.handle_stage_result") as mock_handle:
            mock_wrapped = MagicMock()
            mock_wrapped.side_effect = SystemExit(0)
            mock_handle.return_value = mock_wrapped

            with pytest.raises(SystemExit):
                check_command(ctx, "/test/path")

            mock_handle.assert_called_once()
            mock_wrapped.assert_called_once_with("/test/path")

    def test_check_command_no_path(self):
        """Test check_command shows error when path is None."""
        ctx = MagicMock()
        ctx.get_help.return_value = "help text"

        with patch("wks.api.monitor.app.typer.echo") as mock_echo:
            with patch("wks.api.monitor.app.typer.Exit", side_effect=SystemExit(1)) as mock_exit:
                with pytest.raises(SystemExit) as exc_info:
                    check_command(ctx, None)

                assert exc_info.value.code == 1
                assert mock_echo.call_count == 2
                mock_exit.assert_called_once_with(1)


class TestSyncCommand:
    """Test sync_command wrapper function."""

    def test_sync_command_with_path(self):
        """Test sync_command calls wrapped function when path provided."""
        ctx = MagicMock()

        with patch("wks.api.monitor.app.handle_stage_result") as mock_handle:
            mock_wrapped = MagicMock()
            mock_wrapped.side_effect = SystemExit(0)
            mock_handle.return_value = mock_wrapped

            with pytest.raises(SystemExit):
                sync_command(ctx, "/test/path", False)

            mock_handle.assert_called_once()
            mock_wrapped.assert_called_once_with("/test/path", False)

    def test_sync_command_no_path(self):
        """Test sync_command shows error when path is None."""
        ctx = MagicMock()
        ctx.get_help.return_value = "help text"

        with patch("wks.api.monitor.app.typer.echo") as mock_echo:
            with patch("wks.api.monitor.app.typer.Exit", side_effect=SystemExit(1)) as mock_exit:
                with pytest.raises(SystemExit) as exc_info:
                    sync_command(ctx, None, False)

                assert exc_info.value.code == 1
                assert mock_echo.call_count == 2
                mock_exit.assert_called_once_with(1)


class TestFilterShowCommand:
    """Test filter_show_command wrapper function."""

    def test_filter_show_command_calls_wrapped(self):
        """Test filter_show_command calls wrapped function."""
        ctx = MagicMock()

        with patch("wks.api.monitor.app.handle_stage_result") as mock_handle:
            mock_wrapped = MagicMock()
            mock_wrapped.side_effect = SystemExit(0)
            mock_handle.return_value = mock_wrapped

            with pytest.raises(SystemExit):
                filter_show_command(ctx, "include_paths")

            mock_handle.assert_called_once()
            mock_wrapped.assert_called_once_with("include_paths")


class TestFilterAddCommand:
    """Test filter_add_command wrapper function."""

    def test_filter_add_command_with_args(self):
        """Test filter_add_command calls wrapped function when args provided."""
        ctx = MagicMock()

        with patch("wks.api.monitor.app.handle_stage_result") as mock_handle:
            mock_wrapped = MagicMock()
            mock_wrapped.side_effect = SystemExit(0)
            mock_handle.return_value = mock_wrapped

            with pytest.raises(SystemExit):
                filter_add_command(ctx, "include_paths", "/test")

            mock_handle.assert_called_once()
            mock_wrapped.assert_called_once_with("include_paths", "/test")

    def test_filter_add_command_no_list_name(self):
        """Test filter_add_command shows error when list_name is None."""
        ctx = MagicMock()
        ctx.get_help.return_value = "help text"

        with patch("wks.api.monitor.app.typer.echo") as mock_echo:
            with patch("wks.api.monitor.app.typer.Exit", side_effect=SystemExit(1)) as mock_exit:
                with pytest.raises(SystemExit) as exc_info:
                    filter_add_command(ctx, None, "/test")

                assert exc_info.value.code == 1
                assert mock_echo.call_count == 2
                mock_exit.assert_called_once_with(1)

    def test_filter_add_command_no_value(self):
        """Test filter_add_command shows error when value is None."""
        ctx = MagicMock()
        ctx.get_help.return_value = "help text"

        with patch("wks.api.monitor.app.typer.echo") as mock_echo:
            with patch("wks.api.monitor.app.typer.Exit", side_effect=SystemExit(1)) as mock_exit:
                with pytest.raises(SystemExit) as exc_info:
                    filter_add_command(ctx, "include_paths", None)

                assert exc_info.value.code == 1
                assert mock_echo.call_count == 2
                mock_exit.assert_called_once_with(1)


class TestFilterRemoveCommand:
    """Test filter_remove_command wrapper function."""

    def test_filter_remove_command_with_args(self):
        """Test filter_remove_command calls wrapped function when args provided."""
        ctx = MagicMock()

        with patch("wks.api.monitor.app.handle_stage_result") as mock_handle:
            mock_wrapped = MagicMock()
            mock_wrapped.side_effect = SystemExit(0)
            mock_handle.return_value = mock_wrapped

            with pytest.raises(SystemExit):
                filter_remove_command(ctx, "include_paths", "/test")

            mock_handle.assert_called_once()
            mock_wrapped.assert_called_once_with("include_paths", "/test")

    def test_filter_remove_command_no_list_name(self):
        """Test filter_remove_command shows error when list_name is None."""
        ctx = MagicMock()
        ctx.get_help.return_value = "help text"

        with patch("wks.api.monitor.app.typer.echo") as mock_echo:
            with patch("wks.api.monitor.app.typer.Exit", side_effect=SystemExit(1)) as mock_exit:
                with pytest.raises(SystemExit) as exc_info:
                    filter_remove_command(ctx, None, "/test")

                assert exc_info.value.code == 1
                assert mock_echo.call_count == 2
                mock_exit.assert_called_once_with(1)

    def test_filter_remove_command_no_value(self):
        """Test filter_remove_command shows error when value is None."""
        ctx = MagicMock()
        ctx.get_help.return_value = "help text"

        with patch("wks.api.monitor.app.typer.echo") as mock_echo:
            with patch("wks.api.monitor.app.typer.Exit", side_effect=SystemExit(1)) as mock_exit:
                with pytest.raises(SystemExit) as exc_info:
                    filter_remove_command(ctx, "include_paths", None)

                assert exc_info.value.code == 1
                assert mock_echo.call_count == 2
                mock_exit.assert_called_once_with(1)


class TestPriorityAddCommand:
    """Test priority_add_command wrapper function."""

    def test_priority_add_command_with_args(self):
        """Test priority_add_command calls wrapped function when args provided."""
        ctx = MagicMock()

        with patch("wks.api.monitor.app.handle_stage_result") as mock_handle:
            mock_wrapped = MagicMock()
            mock_wrapped.side_effect = SystemExit(0)
            mock_handle.return_value = mock_wrapped

            with pytest.raises(SystemExit):
                priority_add_command(ctx, "/test", 5.0)

            mock_handle.assert_called_once()
            mock_wrapped.assert_called_once_with("/test", 5.0)

    def test_priority_add_command_no_path(self):
        """Test priority_add_command shows error when path is None."""
        ctx = MagicMock()
        ctx.get_help.return_value = "help text"

        with patch("wks.api.monitor.app.typer.echo") as mock_echo:
            with patch("wks.api.monitor.app.typer.Exit", side_effect=SystemExit(1)) as mock_exit:
                with pytest.raises(SystemExit) as exc_info:
                    priority_add_command(ctx, None, 5.0)

                assert exc_info.value.code == 1
                assert mock_echo.call_count == 2
                mock_exit.assert_called_once_with(1)

    def test_priority_add_command_no_priority(self):
        """Test priority_add_command shows error when priority is None."""
        ctx = MagicMock()
        ctx.get_help.return_value = "help text"

        with patch("wks.api.monitor.app.typer.echo") as mock_echo:
            with patch("wks.api.monitor.app.typer.Exit", side_effect=SystemExit(1)) as mock_exit:
                with pytest.raises(SystemExit) as exc_info:
                    priority_add_command(ctx, "/test", None)

                assert exc_info.value.code == 1
                assert mock_echo.call_count == 2
                mock_exit.assert_called_once_with(1)


class TestPriorityRemoveCommand:
    """Test priority_remove_command wrapper function."""

    def test_priority_remove_command_with_path(self):
        """Test priority_remove_command calls wrapped function when path provided."""
        ctx = MagicMock()

        with patch("wks.api.monitor.app.handle_stage_result") as mock_handle:
            mock_wrapped = MagicMock()
            mock_wrapped.side_effect = SystemExit(0)
            mock_handle.return_value = mock_wrapped

            with pytest.raises(SystemExit):
                priority_remove_command(ctx, "/test")

            mock_handle.assert_called_once()
            mock_wrapped.assert_called_once_with("/test")

    def test_priority_remove_command_no_path(self):
        """Test priority_remove_command shows error when path is None."""
        ctx = MagicMock()
        ctx.get_help.return_value = "help text"

        with patch("wks.api.monitor.app.typer.echo") as mock_echo:
            with patch("wks.api.monitor.app.typer.Exit", side_effect=SystemExit(1)) as mock_exit:
                with pytest.raises(SystemExit) as exc_info:
                    priority_remove_command(ctx, None)

                assert exc_info.value.code == 1
                assert mock_echo.call_count == 2
                mock_exit.assert_called_once_with(1)


def test_monitor_app_wrapper_non_cli():
    """Test handle_stage_result wrapper behavior."""
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

    wrapped = handle_stage_result(lambda: stage)
    # handle_stage_result calls sys.exit() for CLI, so we need to catch SystemExit
    with pytest.raises(SystemExit) as exc_info:
        wrapped()
    # Verify exit code is 0 for success
    assert exc_info.value.code == 0
    assert calls == ["progress"]
