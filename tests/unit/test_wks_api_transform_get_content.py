"""Tests for transform get_content API."""

from pathlib import Path

import pytest

from tests.unit.conftest import run_cmd
from wks.api.transform.cmd_engine import cmd_transform
from wks.api.transform.get_content import get_content


@pytest.mark.transform
def test_get_content_file(wks_home, minimal_config_dict):
    """Test retrieving content for a file."""
    watch_dir = Path(wks_home).parent / "watched"
    watch_dir.mkdir(parents=True, exist_ok=True)

    test_file = watch_dir / "get_me.txt"
    test_file.write_text("Get Content", encoding="utf-8")

    content = get_content(str(test_file))
    assert content == "Transformed: Get Content"


@pytest.mark.transform
def test_get_content_checksum(wks_home, minimal_config_dict):
    """Test retrieving content by checksum."""
    watch_dir = Path(wks_home).parent / "watched"
    watch_dir.mkdir(parents=True, exist_ok=True)

    test_file = watch_dir / "checksum_me.txt"
    test_file.write_text("Checksum Content", encoding="utf-8")

    res = run_cmd(cmd_transform, engine="test", file_path=test_file, overrides={})
    assert res.success is True
    checksum = res.output["checksum"]

    content = get_content(checksum)
    assert content == "Transformed: Checksum Content"
