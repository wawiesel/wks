"""Unit tests for wks.api.config.DisplayConfig module."""

import pytest

from wks.api.config.DisplayConfig import DEFAULT_TIMESTAMP_FORMAT, DisplayConfig

pytestmark = pytest.mark.config


class TestDisplayConfig:
    """Test DisplayConfig dataclass."""

    def test_default_timestamp_format(self):
        """Test DisplayConfig has default timestamp format."""
        config = DisplayConfig()
        assert config.timestamp_format == DEFAULT_TIMESTAMP_FORMAT

    def test_custom_timestamp_format(self):
        """Test DisplayConfig accepts custom timestamp format."""
        config = DisplayConfig(timestamp_format="%H:%M:%S")
        assert config.timestamp_format == "%H:%M:%S"

    def test_from_config_with_custom_format(self):
        """Test from_config with custom timestamp format."""
        cfg = {"display": {"timestamp_format": "%Y-%m-%d"}}
        config = DisplayConfig.from_config(cfg)
        assert config.timestamp_format == "%Y-%m-%d"

    def test_from_config_with_empty_dict(self):
        """Test from_config with empty dict uses default."""
        config = DisplayConfig.from_config({})
        assert config.timestamp_format == DEFAULT_TIMESTAMP_FORMAT

    def test_from_config_without_display_section(self):
        """Test from_config without display section uses default."""
        config = DisplayConfig.from_config({"other": "section"})
        assert config.timestamp_format == DEFAULT_TIMESTAMP_FORMAT

    def test_from_config_with_empty_display_section(self):
        """Test from_config with empty display section uses default."""
        config = DisplayConfig.from_config({"display": {}})
        assert config.timestamp_format == DEFAULT_TIMESTAMP_FORMAT
