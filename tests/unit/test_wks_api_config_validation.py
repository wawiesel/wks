import pytest

from wks.api.config.WKSConfig import WKSConfig


def test_validation_cache_must_be_monitored(minimal_config_dict):
    config_dict = minimal_config_dict.copy()

    config_dict["monitor"]["filter"]["include_paths"] = ["/some/other/path"]
    config_dict["transform"]["cache"]["base_dir"] = "/tmp/wks_unmonitored_cache"

    with pytest.raises(ValueError, match="is not monitored"):
        WKSConfig(**config_dict)


def test_validation_cache_must_not_be_excluded(minimal_config_dict):
    config_dict = minimal_config_dict.copy()

    cache_dir = config_dict["transform"]["cache"]["base_dir"]
    config_dict["monitor"]["filter"]["include_paths"] = [cache_dir]

    config_dict["monitor"]["filter"]["exclude_paths"] = [cache_dir]

    with pytest.raises(ValueError, match="is not monitored"):
        WKSConfig(**config_dict)


def test_validation_cache_must_not_be_in_wks_home(minimal_config_dict, monkeypatch, tmp_path):
    wks_home = tmp_path / "wks_home"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    config_dict = minimal_config_dict.copy()

    cache_dir = str(wks_home / "cache")
    config_dict["transform"]["cache"]["base_dir"] = cache_dir
    config_dict["monitor"]["filter"]["include_paths"] = [cache_dir]

    with pytest.raises(ValueError, match="In WKS home directory"):
        WKSConfig(**config_dict)
