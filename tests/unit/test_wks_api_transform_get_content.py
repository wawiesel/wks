"""Tests for transform get_content API."""

from pathlib import Path

import pytest

from tests.unit.conftest import run_cmd
from wks.api.transform.cmd_engine import cmd_engine
from wks.api.transform.get_content import get_content
from wks.api.URI import URI


@pytest.mark.transform
def test_get_content_file(wks_home, minimal_config_dict):
    """Test retrieving content for a file."""
    watch_dir = Path(wks_home).parent / "watched"
    watch_dir.mkdir(parents=True, exist_ok=True)

    test_file = watch_dir / "get_me.txt"
    test_file.write_text("Get Content", encoding="utf-8")

    # First transform it to ensure it's in the system
    run_cmd(cmd_engine, engine="test", uri=URI.from_path(test_file), overrides={})

    content = get_content(str(test_file))
    assert content == "Transformed: Get Content"


@pytest.mark.transform
def test_get_content_checksum(wks_home, minimal_config_dict):
    """Test retrieving content by checksum."""
    watch_dir = Path(wks_home).parent / "watched"
    watch_dir.mkdir(parents=True, exist_ok=True)

    test_file = watch_dir / "checksum_me.txt"
    test_file.write_text("Checksum Content", encoding="utf-8")

    res = run_cmd(cmd_engine, engine="test", uri=URI.from_path(test_file), overrides={})
    assert res.success is True
    checksum = res.output["checksum"]

    content = get_content(checksum)
    assert content == "Transformed: Checksum Content"


@pytest.mark.transform
def test_get_content_missing_checksum(wks_home, minimal_config_dict):
    """Test retrieving content for missing checksum."""
    with pytest.raises(ValueError) as excinfo:
        get_content("0000000000000000000000000000000000000000000000000000000000000000")
    assert "not found" in str(excinfo.value)


@pytest.mark.transform
def test_get_content_missing_file(wks_home, minimal_config_dict):
    """Test retrieving content for missing file path."""
    with pytest.raises(ValueError) as excinfo:
        get_content("/non/existent/path.txt")
    assert "not found" in str(excinfo.value)


@pytest.mark.transform
def test_get_content_to_output_file(wks_home, minimal_config_dict, tmp_path):
    """Test retrieving content and writing to output file."""
    watch_dir = Path(wks_home).parent / "watched"
    watch_dir.mkdir(parents=True, exist_ok=True)

    test_file = watch_dir / "output_me.txt"
    test_file.write_text("Output Content", encoding="utf-8")
    run_cmd(cmd_engine, engine="test", uri=URI.from_path(test_file), overrides={})

    out_file = tmp_path / "out.md"
    get_content(str(test_file), output_path=out_file)
    assert out_file.exists()
    assert out_file.read_text() == "Transformed: Output Content"
