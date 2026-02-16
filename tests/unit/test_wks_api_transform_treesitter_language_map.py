"""Unit tests for wks.api.transform._treesitter._language_map.resolve_language."""

from pathlib import Path

import pytest

from wks.api.transform._treesitter._language_map import resolve_language


def test_explicit_language():
    """Explicit language option returned directly."""
    result = resolve_language(Path("file.txt"), {"language": "rust"})
    assert result == "rust"


def test_auto_with_known_extension():
    """Auto language resolves from file extension."""
    result = resolve_language(Path("script.py"), {"language": "auto"})
    assert result == "python"


def test_auto_with_mime_override():
    """mime_type option overrides extension-based detection."""
    result = resolve_language(Path("file.xyz"), {"language": "auto", "mime_type": "text/x-python"})
    assert result == "python"


def test_auto_unknown_raises():
    """Unknown extension and no MIME raises ValueError."""
    with pytest.raises(ValueError, match="recognizable"):
        resolve_language(Path("file.zzz"), {"language": "auto"})


def test_explicit_empty_raises():
    """Empty language string raises ValueError."""
    with pytest.raises(ValueError, match="non-empty string"):
        resolve_language(Path("file.py"), {"language": ""})


def test_mime_type_non_string_raises():
    """Non-string mime_type raises ValueError."""
    with pytest.raises(ValueError, match="must be a string"):
        resolve_language(Path("file.py"), {"language": "auto", "mime_type": 123})
