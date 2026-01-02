"""MCP Smoke Tests.

These tests run the MCP server in a subprocess and communicate via stdio.
They ensure the installed MCP server works end-to-end through the JSON-RPC protocol.
These verify that the installed package's MCP capabilities work correctly.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.conftest import check_mongod_available, get_mongo_connection_info


def _find_wksc_command():
    """Find the installed wksc command.

    Prefers venv/bin/wksc if available, otherwise searches PATH.
    """
    # Check for venv in project root
    project_root = Path(__file__).parents[2]
    venv_wksc = project_root / ".venv" / "bin" / "wksc"
    if venv_wksc.exists():
        return str(venv_wksc)

    # Fall back to system PATH
    wksc_path = shutil.which("wksc")
    if wksc_path:
        return wksc_path

    # If not found, raise error with helpful message
    raise RuntimeError("wksc command not found. Please install the package: pip install -e .")


def _get_wks_mcp_cmd():
    """Get the wksc mcp command path (lazy evaluation)."""
    return [_find_wksc_command(), "mcp", "run", "--direct"]


def _require_mongod() -> None:
    """Fail loudly if MongoDB requirements are not met."""
    if not check_mongod_available():
        pytest.fail("MCP smoke tests require `mongod` in PATH. Install MongoDB so `mongod --version` works.")


@pytest.fixture(scope="module")
def mcp_process(tmp_path_factory):
    """Start MCP server process."""
    _require_mongod()

    env_dir = tmp_path_factory.mktemp("mcp_env")
    home_dir = env_dir / "home"
    home_dir.mkdir()

    # Set HOME to the temp dir to isolate config
    env = os.environ.copy()
    env["HOME"] = str(home_dir)
    # Override WKS_HOME to ensure config is loaded from temp dir
    env["WKS_HOME"] = str(home_dir / ".wks")

    # Symlink .local from real HOME to temp HOME so pip install --user packages are visible
    real_home = Path(os.environ["HOME"])
    if (real_home / ".local").exists():
        (home_dir / ".local").symlink_to(real_home / ".local")

    # Don't add PYTHONPATH - we're testing the installed package, not the source
    # The installed wksc should work without PYTHONPATH manipulation

    (home_dir / ".wks").mkdir()
    # Build a valid config using shared helpers, then override DB to use local Mongo.
    from tests.conftest import minimal_config_dict

    config = minimal_config_dict()

    mongo_uri, _, is_local = get_mongo_connection_info(home_dir)

    config["database"] = {
        "type": "mongo",
        "prefix": "wks_mcp_smoke",
        "data": {
            "uri": mongo_uri,
            "local": is_local,
        },
    }
    # Ensure monitor has at least one include path so monitor_check can succeed for an in-scope path.
    # ALSO: ensure transform cache is monitored (required by validator)
    cache_dir = home_dir / "transform_cache"
    config["transform"]["cache"]["base_dir"] = str(cache_dir)
    config["monitor"]["filter"]["include_paths"] = [str(home_dir), str(cache_dir)]

    (home_dir / ".wks" / "config.json").write_text(json.dumps(config), encoding="utf-8")

    # Start process using installed wksc command
    cmd = _get_wks_mcp_cmd()
    process = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        text=True,
        bufsize=0,  # Unbuffered
    )

    yield process

    process.terminate()
    process.wait()


def send_request(process, method, params=None, req_id=1):
    """Send JSON-RPC request and get response."""
    request = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params or {}}

    # Write request
    try:
        process.stdin.write(json.dumps(request) + "\n")
        process.stdin.flush()
    except (BrokenPipeError, ValueError):
        # Process died unexpectedly. Capture stderr for debugging.
        try:
            _, errs = process.communicate(timeout=1)
            err = errs if errs else ""
        except Exception:
            err = "Could not retrieve stderr."
        raise AssertionError(f"MCP process died unexpectedly when sending request. STDERR:\n{err}") from None

    # Read response
    line = process.stdout.readline()
    if not line:
        # Fail loudly with stderr context (common when MCP process exits on startup).
        try:
            rc = process.poll()
        except Exception:
            rc = None
        try:
            # If we can read more stderr, do so (non-blocking if possible, but here we likely can just read)
            # Use communicate to safely get rest of output
            _, err_full = process.communicate(timeout=1)
            err = err_full if err_full else ""
        except Exception:
            err = ""
        raise AssertionError(f"No response from MCP process (returncode={rc}). STDERR:\n{err}")

    return json.loads(line)


def test_mcp_initialize(mcp_process):
    """Test initialize."""
    response = send_request(mcp_process, "initialize")
    assert response["result"]["serverInfo"]["name"] == "wks-mcp-server"


def test_mcp_list_tools(mcp_process):
    """Test tools/list."""
    response = send_request(mcp_process, "tools/list", req_id=2)
    tools = response["result"]["tools"]
    assert any(t["name"] == "wksm_monitor_status" for t in tools)


def test_mcp_call_monitor_status(mcp_process):
    """Test tools/call wks_monitor_status."""
    response = send_request(mcp_process, "tools/call", {"name": "wksm_monitor_status", "arguments": {}}, req_id=3)

    content = json.loads(response["result"]["content"][0]["text"])
    assert "data" in content
    assert "tracked_files" in content["data"]


def test_mcp_call_monitor_check(mcp_process):
    """Test tools/call wks_monitor_check."""
    response = send_request(
        mcp_process,
        "tools/call",
        {"name": "wksm_monitor_check", "arguments": {"path": str(Path.home())}},
        req_id=4,
    )

    content = json.loads(response["result"]["content"][0]["text"])
    assert "data" in content
    assert "is_monitored" in content["data"]
