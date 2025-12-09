"""Unit tests for wks.api.config.app module."""

from unittest.mock import MagicMock, patch

import pytest
import typer

from wks.cli.config import config_app, list_command, show_command, version_command

pytestmark = pytest.mark.config


class TestConfigApp:
    """Test config_app Typer app."""

    def test_config_app_is_typer(self):
        """Test config_app is a Typer instance."""
        assert isinstance(config_app, typer.Typer)
        assert config_app.info.name == "config"

    def test_list_command_invokes_handler(self):
        """list_command should wrap cmd_list and execute."""
        with patch("wks.cli.config.handle_stage_result") as mock_handle:
            mock_wrapped = MagicMock()
            mock_wrapped.side_effect = SystemExit(0)
            mock_handle.return_value = mock_wrapped
            with pytest.raises(SystemExit):
                list_command()
            mock_handle.assert_called_once()
            mock_wrapped.assert_called_once_with()

    def test_show_command_invokes_handler(self):
        """show_command should wrap cmd_show and require section."""
        with patch("wks.cli.config.handle_stage_result") as mock_handle:
            mock_wrapped = MagicMock()
            mock_wrapped.side_effect = SystemExit(0)
            mock_handle.return_value = mock_wrapped
            with pytest.raises(SystemExit):
                show_command("monitor")
            mock_handle.assert_called_once()
            mock_wrapped.assert_called_once_with("monitor")

    def test_version_command_invokes_handler(self):
        """version_command should wrap cmd_version and execute."""
        with patch("wks.cli.config.handle_stage_result") as mock_handle:
            mock_wrapped = MagicMock()
            mock_wrapped.side_effect = SystemExit(0)
            mock_handle.return_value = mock_wrapped
            with pytest.raises(SystemExit):
                version_command()
            mock_handle.assert_called_once()
            mock_wrapped.assert_called_once_with()
