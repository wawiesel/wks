"""Tests for diff engine registry."""

from wks.api.diff import ENGINES


def test_diff_engines_keys_match_spec() -> None:
    assert set(ENGINES.keys()) == {"bsdiff3", "myers", "sexp"}


def test_bsdiff3_engine_class_name() -> None:
    assert "Bsdiff3" in ENGINES["bsdiff3"].__class__.__name__


def test_sexp_engine_class_name() -> None:
    assert "Sexp" in ENGINES["sexp"].__class__.__name__
