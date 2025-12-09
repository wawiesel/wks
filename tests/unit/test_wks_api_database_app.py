"""Unit tests for wks.api.database.app module."""

from unittest.mock import MagicMock, patch

import pytest
import typer

from wks.api.database.app import db_app, db_callback, reset_command, show_command

pytestmark = pytest.mark.db


class TestDbApp:
    """Test db_app Typer app."""

    def test_db_app_is_typer(self):
        """Test db_app is a Typer instance."""
        assert isinstance(db_app, typer.Typer)
        assert db_app.info.name == "database"

    def test_db_callback_without_subcommand(self):
        """Test db_callback shows help when no subcommand."""
        ctx = MagicMock()
        ctx.invoked_subcommand = None
        ctx.get_help.return_value = "help text"

        with patch("wks.api.database.app.typer.echo") as mock_echo:
            with patch("wks.api.database.app.typer.Exit", side_effect=SystemExit) as mock_exit:
                with pytest.raises(SystemExit):
                    db_callback(ctx)
                mock_echo.assert_called_once_with("help text", err=True)
                mock_exit.assert_called_once()

    def test_db_callback_with_subcommand(self):
        """Test db_callback does nothing when subcommand exists."""
        ctx = MagicMock()
        ctx.invoked_subcommand = "show"

        # Should not raise
        db_callback(ctx)


class TestShowCommand:
    """Test show_command wrapper function."""

    def test_show_command_with_collection(self):
        """Test show_command calls wrapped function when collection provided."""
        ctx = MagicMock()

        with patch("wks.api.database.app.handle_stage_result") as mock_handle:
            mock_wrapped = MagicMock()
            mock_wrapped.side_effect = SystemExit(0)
            mock_handle.return_value = mock_wrapped

            with pytest.raises(SystemExit):
                show_command(ctx, "monitor", None, 50)

            mock_handle.assert_called_once()
            mock_wrapped.assert_called_once_with("monitor", None, 50)

    def test_show_command_no_collection(self):
        """Test show_command shows error when collection is None."""
        ctx = MagicMock()
        ctx.get_help.return_value = "help text"

        with patch("wks.api.database.app.typer.echo") as mock_echo:
            with patch("wks.api.database.app.typer.Exit", side_effect=SystemExit(1)) as mock_exit:
                with pytest.raises(SystemExit) as exc_info:
                    show_command(ctx, None, None, 50)

                assert exc_info.value.code == 1
                assert mock_echo.call_count == 2  # Error message + help
                mock_exit.assert_called_once_with(1)


class TestResetCommand:
    """Test reset_command wrapper function."""

    def test_reset_command_with_collection(self):
        """Test reset_command calls wrapped function when collection provided."""
        ctx = MagicMock()

        with patch("wks.api.database.app.handle_stage_result") as mock_handle:
            mock_wrapped = MagicMock()
            mock_wrapped.side_effect = SystemExit(0)
            mock_handle.return_value = mock_wrapped

            with pytest.raises(SystemExit):
                reset_command(ctx, "monitor")

            mock_handle.assert_called_once()
            mock_wrapped.assert_called_once_with("monitor")

    def test_reset_command_no_collection(self):
        """Test reset_command shows error when collection is None."""
        ctx = MagicMock()
        ctx.get_help.return_value = "help text"

        with patch("wks.api.database.app.typer.echo") as mock_echo:
            with patch("wks.api.database.app.typer.Exit", side_effect=SystemExit(1)) as mock_exit:
                with pytest.raises(SystemExit) as exc_info:
                    reset_command(ctx, None)

                assert exc_info.value.code == 1
                assert mock_echo.call_count == 2  # Error message + help
                mock_exit.assert_called_once_with(1)
