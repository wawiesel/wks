"""Tests for wks/api/cat/cmd.py."""

from pathlib import Path

import pytest

from tests.unit.conftest import run_cmd
from wks.api.cat.cmd import cmd
from wks.api.database.Database import Database
from wks.api.transform.cmd_engine import cmd_transform


@pytest.mark.cat
def test_cmd_by_path(wks_home, minimal_config_dict):
    """Test retrieving content by file path (triggers transform)."""
    watch_dir = Path(wks_home).parent / "watched"
    watch_dir.mkdir(parents=True, exist_ok=True)

    test_file = watch_dir / "test.txt"
    test_file.write_text("Hello Cat", encoding="utf-8")

    # cmd by path
    res = run_cmd(cmd, target=str(test_file))
    assert res.success is True
    assert res.output["content"] == "Transformed: Hello Cat"
    assert "target" in res.output


@pytest.mark.cat
def test_cmd_by_checksum(wks_home, minimal_config_dict):
    """Test retrieving content by checksum (direct lookup)."""
    watch_dir = Path(wks_home).parent / "watched"
    watch_dir.mkdir(parents=True, exist_ok=True)

    test_file = watch_dir / "test.txt"
    test_file.write_text("Checksum Cat", encoding="utf-8")

    # 1. Transform to get checksum
    res_t = run_cmd(cmd_transform, engine="test", file_path=test_file, overrides={})
    assert res_t.success is True
    checksum = res_t.output["checksum"]

    # 2. cmd by checksum
    res = run_cmd(cmd, target=checksum)
    assert res.success is True
    assert res.output["content"] == "Transformed: Checksum Cat"


@pytest.mark.cat
def test_cmd_to_output_file(wks_home, minimal_config_dict):
    """Test retrieving content and saving to an output file."""
    watch_dir = Path(wks_home).parent / "watched"
    watch_dir.mkdir(parents=True, exist_ok=True)

    test_file = watch_dir / "test.txt"
    test_file.write_text("Output File Content", encoding="utf-8")

    out_file = watch_dir / "output.md"

    # cmd with output_path
    res = run_cmd(cmd, target=str(test_file), output_path=out_file)
    assert res.success is True
    assert out_file.exists()
    assert out_file.read_text() == "Transformed: Output File Content"


@pytest.mark.cat
def test_cmd_nonexistent_file(wks_home):
    """Test cmd with a missing file."""
    res = run_cmd(cmd, target="/tmp/nonexistent_file_12345")
    assert res.success is False
    assert "File not found" in res.result


@pytest.mark.cat
def test_cmd_nonexistent_checksum(wks_home):
    """Test cmd with a missing checksum."""
    missing_checksum = "a" * 64
    res = run_cmd(cmd, target=missing_checksum)
    assert res.success is False
    assert "Checksum not found in database" in res.result


@pytest.mark.cat
def test_cmd_stale_cache_record(wks_home, minimal_config_dict):
    """Test cmd when DB has record but file is missing from disk."""
    watch_dir = Path(wks_home).parent / "watched"
    watch_dir.mkdir(parents=True, exist_ok=True)

    test_file = watch_dir / "stale.txt"
    test_file.write_text("Stale Content", encoding="utf-8")

    # 1. Transform to populate DB and cache
    res_t = run_cmd(cmd_transform, engine="test", file_path=test_file, overrides={})
    assert res_t.success is True
    checksum = res_t.output["checksum"]

    # 2. Manually delete the cache file
    cache_dir = Path(minimal_config_dict["transform"]["cache"]["base_dir"])
    for f in cache_dir.glob(f"{checksum}.*"):
        f.unlink()

    # 3. cmd should fail and clean up DB record
    res = run_cmd(cmd, target=checksum)
    assert res.success is False
    assert "Cache file not found" in res.result

    # 4. Verify DB record is gone
    from wks.api.config.WKSConfig import WKSConfig

    config = WKSConfig.load()
    with Database(config.database, "transform") as db:
        assert db.find_one({"checksum": checksum}) is None
