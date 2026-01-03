"""Tests for WKSConfig validation rules, specifically cache-monitor consistency."""

import pytest

from wks.api.config.WKSConfig import WKSConfig


def test_validation_cache_must_be_monitored(minimal_config_dict):
    """Test that WKSConfig rejects cache directories that are not in include_paths."""
    config_dict = minimal_config_dict.copy()

    # Set cache to something NOT in include_paths
    # minimal_config_dict fixture puts it in 'transform_cache' and adds that to include_paths.
    # We clear include_paths to trigger the error.
    config_dict["monitor"]["filter"]["include_paths"] = ["/some/other/path"]
    config_dict["transform"]["cache"]["base_dir"] = "/tmp/wks_unmonitored_cache"

    with pytest.raises(ValueError, match="is not monitored"):
        WKSConfig(**config_dict)


def test_validation_cache_must_not_be_excluded(minimal_config_dict):
    """Test that WKSConfig rejects cache directories that are explicitly excluded."""
    config_dict = minimal_config_dict.copy()

    cache_dir = config_dict["transform"]["cache"]["base_dir"]
    # Add it to include_paths (fixture already does this, but let's be explicit)
    config_dict["monitor"]["filter"]["include_paths"] = [cache_dir]

    # Exclude it
    config_dict["monitor"]["filter"]["exclude_paths"] = [cache_dir]

    with pytest.raises(ValueError, match="is not monitored"):
        WKSConfig(**config_dict)


def test_validation_cache_must_not_be_in_wks_home(minimal_config_dict, monkeypatch, tmp_path):
    """Test that WKSConfig rejects cache directories inside WKS_HOME."""
    wks_home = tmp_path / "wks_home"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    config_dict = minimal_config_dict.copy()

    # Put cache inside WKS_HOME
    cache_dir = str(wks_home / "cache")
    config_dict["transform"]["cache"]["base_dir"] = cache_dir
    config_dict["monitor"]["filter"]["include_paths"] = [cache_dir]

    with pytest.raises(ValueError, match="In WKS home directory"):
        WKSConfig(**config_dict)
