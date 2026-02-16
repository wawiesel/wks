"""Unit tests for wks.api.transform.post_reset."""

from wks.api.config.WKSConfig import WKSConfig
from wks.api.transform.post_reset import post_reset


def test_post_reset_deletes_expected_extensions(wks_home, minimal_config_dict, tmp_path):
    """post_reset deletes .md, .txt, .json files but keeps others."""
    config = WKSConfig.load()

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    config.transform.cache.base_dir = str(cache_dir)
    config.save()

    # Create files with different extensions
    md_file = cache_dir / "doc.md"
    txt_file = cache_dir / "notes.txt"
    json_file = cache_dir / "data.json"
    bin_file = cache_dir / "image.bin"

    for f in (md_file, txt_file, json_file, bin_file):
        f.write_text("content")

    post_reset(config)

    assert not md_file.exists(), ".md should be deleted"
    assert not txt_file.exists(), ".txt should be deleted"
    assert not json_file.exists(), ".json should be deleted"
    assert bin_file.exists(), ".bin should be kept"


def test_post_reset_no_cache_dir(wks_home, minimal_config_dict, tmp_path):
    """post_reset does nothing when cache dir doesn't exist."""
    config = WKSConfig.load()
    config.transform.cache.base_dir = str(tmp_path / "nonexistent")
    config.save()

    # Should not raise
    post_reset(config)
