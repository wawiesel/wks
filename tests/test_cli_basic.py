"""Basic CLI tests - tests for wks/cli/__init__.py."""

import io
from contextlib import redirect_stdout, redirect_stderr

try:
    import importlib.metadata as importlib_metadata
except ImportError:  # pragma: no cover
    import importlib_metadata  # type: ignore


def run_cli(args):
    """Execute CLI command and capture stdout/stderr."""
    from wks.cli import main

    out_buf = io.StringIO()
    err_buf = io.StringIO()
    with redirect_stdout(out_buf), redirect_stderr(err_buf):
        try:
            rc = main(args)
        except SystemExit as exc:  # CLI exits on errors/--json flows
            rc = exc.code if isinstance(exc.code, int) else 0
    return rc, out_buf.getvalue(), err_buf.getvalue()


def test_cli_version_flag():
    """Test --version flag."""
    rc, out, _ = run_cli(['--version'])
    assert rc == 0
    expected = importlib_metadata.version('wks')
    assert f"wksc {expected}" in out


def test_cli_help_flag():
    """Test --help flag."""
    rc, out, _ = run_cli(['--help'])
    assert rc == 0
    assert "usage:" in out.lower() or "wksc" in out.lower()
