"""Tests for binary pass-through transform engine via cmd_engine."""

import pytest

from tests.unit.conftest import create_tracked_wks_config, run_cmd
from wks.api.config.URI import URI
from wks.api.transform.cmd_engine import cmd_engine

pytestmark = pytest.mark.unit


def test_binarypass_copies_content(tmp_path, monkeypatch, minimal_config_dict):
    """Binarypass engine copies binary content to cache."""
    minimal_config_dict["transform"]["engines"]["bp"] = {"type": "binarypass", "data": {}}
    create_tracked_wks_config(monkeypatch, config_dict=minimal_config_dict)

    source = tmp_path / "data.bin"
    source.write_bytes(b"\x00\x01\x02\xff\xfe\xfd")

    result = run_cmd(cmd_engine, engine="bp", uri=URI.from_path(source), overrides={})
    assert result.success is True
    destination = URI(result.output["destination_uri"]).path
    assert destination.exists()
    assert destination.read_bytes() == b"\x00\x01\x02\xff\xfe\xfd"


def test_binarypass_output_extension(tmp_path, monkeypatch, minimal_config_dict):
    """Binarypass engine produces .bin output extension."""
    minimal_config_dict["transform"]["engines"]["bp"] = {"type": "binarypass", "data": {}}
    create_tracked_wks_config(monkeypatch, config_dict=minimal_config_dict)

    source = tmp_path / "data.bin"
    source.write_bytes(b"\x00\x01")

    result = run_cmd(cmd_engine, engine="bp", uri=URI.from_path(source), overrides={})
    assert result.success is True
    destination = URI(result.output["destination_uri"]).path
    assert destination.suffix == ".bin"


def test_binarypass_caching(tmp_path, monkeypatch, minimal_config_dict):
    """Binarypass engine caches results on second run."""
    minimal_config_dict["transform"]["engines"]["bp"] = {"type": "binarypass", "data": {}}
    create_tracked_wks_config(monkeypatch, config_dict=minimal_config_dict)

    source = tmp_path / "data.bin"
    source.write_bytes(b"\x00\x01\x02")

    res1 = run_cmd(cmd_engine, engine="bp", uri=URI.from_path(source), overrides={})
    assert res1.success is True
    assert res1.output["cached"] is False

    res2 = run_cmd(cmd_engine, engine="bp", uri=URI.from_path(source), overrides={})
    assert res2.success is True
    assert res2.output["cached"] is True
    assert res2.output["checksum"] == res1.output["checksum"]
