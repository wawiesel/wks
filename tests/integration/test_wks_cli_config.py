"""Integration tests for wks.cli.config module."""

from unittest.mock import MagicMock, patch

import pytest
import typer

from wks.cli.config import config_app, config_callback

pytestmark = pytest.mark.integration


class TestConfigApp:
    """Test config_app Typer app."""

    def test_config_app_is_typer(self):
        """Test config_app is a Typer instance."""
        assert isinstance(config_app, typer.Typer)
        assert config_app.info.name == "config"

    def test_config_callback_without_subcommand(self, monkeypatch):
        """Test config_callback handles no subcommand."""
        ctx = MagicMock()
        ctx.invoked_subcommand = None

        with patch("wks.cli.config.handle_stage_result") as mock_handle:
            mock_wrapped = MagicMock()
            mock_wrapped.side_effect = SystemExit(0)
            mock_handle.return_value = mock_wrapped
            with pytest.raises(SystemExit):
                config_callback(ctx, None)
            mock_handle.assert_called_once()
            mock_wrapped.assert_called_once_with("")

    def test_config_callback_with_subcommand(self, monkeypatch):
        """Test config_callback does nothing when subcommand is invoked."""
        ctx = MagicMock()
        ctx.invoked_subcommand = "show"

        # Should not raise or do anything when subcommand exists
        config_callback(ctx, None)
