"""Unit tests for wks.api.config.MetricsConfig module."""

import pytest

from wks.api.config.MetricsConfig import MetricsConfig

pytestmark = pytest.mark.config


class TestMetricsConfig:
    """Test MetricsConfig dataclass."""

    def test_default_values(self):
        """Test MetricsConfig has correct default values."""
        config = MetricsConfig()
        assert config.fs_rate_short_window_secs == 10.0
        assert config.fs_rate_long_window_secs == 600.0
        assert config.fs_rate_short_weight == 0.8
        assert config.fs_rate_long_weight == 0.2

    def test_custom_values(self):
        """Test MetricsConfig accepts custom values."""
        config = MetricsConfig(
            fs_rate_short_window_secs=5.0,
            fs_rate_long_window_secs=300.0,
            fs_rate_short_weight=0.9,
            fs_rate_long_weight=0.1,
        )
        assert config.fs_rate_short_window_secs == 5.0
        assert config.fs_rate_long_window_secs == 300.0
        assert config.fs_rate_short_weight == 0.9
        assert config.fs_rate_long_weight == 0.1

    def test_from_config_with_all_values(self):
        """Test from_config with all values."""
        cfg = {
            "metrics": {
                "fs_rate_short_window_secs": 5.0,
                "fs_rate_long_window_secs": 300.0,
                "fs_rate_short_weight": 0.9,
                "fs_rate_long_weight": 0.1,
            }
        }
        config = MetricsConfig.from_config(cfg)
        assert config.fs_rate_short_window_secs == 5.0
        assert config.fs_rate_long_window_secs == 300.0
        assert config.fs_rate_short_weight == 0.9
        assert config.fs_rate_long_weight == 0.1

    def test_from_config_with_partial_values(self):
        """Test from_config with partial values uses defaults for missing."""
        cfg = {
            "metrics": {
                "fs_rate_short_window_secs": 5.0,
            }
        }
        config = MetricsConfig.from_config(cfg)
        assert config.fs_rate_short_window_secs == 5.0
        assert config.fs_rate_long_window_secs == 600.0  # default
        assert config.fs_rate_short_weight == 0.8  # default
        assert config.fs_rate_long_weight == 0.2  # default

    def test_from_config_with_empty_dict(self):
        """Test from_config with empty dict uses defaults."""
        config = MetricsConfig.from_config({})
        assert config.fs_rate_short_window_secs == 10.0
        assert config.fs_rate_long_window_secs == 600.0
        assert config.fs_rate_short_weight == 0.8
        assert config.fs_rate_long_weight == 0.2

    def test_from_config_without_metrics_section(self):
        """Test from_config without metrics section uses defaults."""
        config = MetricsConfig.from_config({"other": "section"})
        assert config.fs_rate_short_window_secs == 10.0
        assert config.fs_rate_long_window_secs == 600.0
        assert config.fs_rate_short_weight == 0.8
        assert config.fs_rate_long_weight == 0.2

    def test_from_config_with_empty_metrics_section(self):
        """Test from_config with empty metrics section uses defaults."""
        config = MetricsConfig.from_config({"metrics": {}})
        assert config.fs_rate_short_window_secs == 10.0
        assert config.fs_rate_long_window_secs == 600.0
        assert config.fs_rate_short_weight == 0.8
        assert config.fs_rate_long_weight == 0.2
