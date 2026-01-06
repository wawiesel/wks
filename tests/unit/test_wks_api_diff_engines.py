"""Tests for diff engine registry."""

from wks.api.diff import ENGINES


def test_diff_engines_keys_match_spec() -> None:
    assert set(ENGINES.keys()) == {"ast", "bsdiff4", "myers"}


def test_bsdiff4_engine_class_name() -> None:
    assert "Bsdiff4" in ENGINES["bsdiff4"].__class__.__name__
