"""Tests for display context helpers."""

import argparse
import sys

from wks.cli.display import CLIDisplay
from wks.utils.display.context import add_display_argument, get_display, is_mcp_context


def test_get_display_returns_cli_for_all_modes():
    """get_display always returns CLI display (MCP bypasses display layer)."""
    assert isinstance(get_display("cli"), CLIDisplay)
    assert isinstance(get_display("mcp"), CLIDisplay)
    assert isinstance(get_display(), CLIDisplay)


def test_is_mcp_context_env_var_detection(monkeypatch):
    """MCP_MODE or MCP_SERVER force MCP detection."""
    monkeypatch.setenv("MCP_MODE", "1")
    assert is_mcp_context() is True

    monkeypatch.delenv("MCP_MODE", raising=False)
    monkeypatch.setenv("MCP_SERVER", "1")
    assert is_mcp_context() is True


def test_is_mcp_context_piped_stdout(monkeypatch):
    """When TERM is missing and stdout is not a TTY, MCP is assumed."""
    monkeypatch.delenv("MCP_MODE", raising=False)
    monkeypatch.delenv("MCP_SERVER", raising=False)
    monkeypatch.delenv("TERM", raising=False)

    original_isatty = sys.stdout.isatty
    sys.stdout.isatty = lambda: False  # type: ignore[assignment]
    try:
        assert is_mcp_context() is True
    finally:
        sys.stdout.isatty = original_isatty


def test_is_mcp_context_false_with_terminal(monkeypatch):
    """With a TTY and no MCP markers, we stay in CLI mode."""
    monkeypatch.delenv("MCP_MODE", raising=False)
    monkeypatch.delenv("MCP_SERVER", raising=False)
    monkeypatch.setenv("TERM", "xterm")

    assert is_mcp_context() is False


def test_add_display_argument(monkeypatch):
    """add_display_argument wires up the flag with auto-detected default."""
    monkeypatch.setenv("TERM", "xterm")
    parser = argparse.ArgumentParser()
    add_display_argument(parser)

    args = parser.parse_args(["--display", "mcp"])
    assert args.display == "mcp"
