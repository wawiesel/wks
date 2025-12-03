"""Tests for transform engine registry."""

from wks.transform.engines import DoclingEngine, TestEngine, get_engine


def test_get_engine_docling():
    """Get docling engine."""
    engine = get_engine("docling")

    assert engine is not None
    assert isinstance(engine, DoclingEngine)


def test_get_engine_test():
    """Get test engine."""
    engine = get_engine("test")

    assert engine is not None
    assert isinstance(engine, TestEngine)


def test_get_engine_unknown():
    """Get unknown engine returns None."""
    engine = get_engine("unknown")

    assert engine is None
