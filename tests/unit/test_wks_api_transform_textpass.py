"""Tests for text pass-through transform engine via cmd_engine."""

import pytest

from tests.unit.conftest import run_cmd
from wks.api.config.URI import URI
from wks.api.transform.cmd_engine import cmd_engine

pytestmark = pytest.mark.unit


def test_textpass_non_utf8_input(tracked_wks_config, tmp_path):
    """TextPass engine fails on non-UTF-8 input."""
    source = tmp_path / "bad.txt"
    source.write_bytes(b"\x80\x81\x82\xff")

    result = run_cmd(cmd_engine, engine="textpass", uri=URI.from_path(source), overrides={})
    assert result.success is False
    assert "utf-8" in result.result.lower() or "utf" in result.result.lower()
