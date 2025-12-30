"""Unit tests for wks.api.__init__ module."""

import wks.api


def test_api_init_docstring():
    """Verify wks.api module docstring."""
    assert wks.api.__doc__ == "API module for WKS commands."
