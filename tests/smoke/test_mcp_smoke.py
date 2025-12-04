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
    return [_find_wksc_command(), "mcp", "--direct"]


def _mongo_available():
    """Check if MongoDB is available."""
    try:
        from pymongo import MongoClient

        client: MongoClient = MongoClient("mongodb://localhost:27017", serverSelectionTimeoutMS=2000)
        client.server_info()
        client.close()
        return True
    except Exception:
        return False


@pytest.fixture(scope="module")
def mcp_process(tmp_path_factory):
    """Start MCP server process."""
    if not _mongo_available():
        pytest.skip("MongoDB not available")

    env_dir = tmp_path_factory.mktemp("mcp_env")
    home_dir = env_dir / "home"
    home_dir.mkdir()

    # Set HOME to the temp dir to isolate config
    env = os.environ.copy()
    env["HOME"] = str(home_dir)

    # Don't add PYTHONPATH - we're testing the installed package, not the source
    # The installed wksc should work without PYTHONPATH manipulation

    # Create config in current WKSConfig / DiffConfig format
    (home_dir / ".wks").mkdir()
    config = {
        "monitor": {
            "include_paths": ["~"],
            "exclude_paths": [],
            "include_dirnames": [],
            "exclude_dirnames": [],
            "include_globs": [],
            "exclude_globs": [],
            "managed_directories": {"~": 100},
            "priority": {"depth_multiplier": 0.9},
            "database": "wks.monitor",
            "max_documents": 10000,
            "prune_interval_secs": 3600,
        },
        "vault": {
            "base_dir": str(home_dir / "Vault"),
            "database": "wks.vault",
            "wks_dir": "WKS",
            "update_frequency_seconds": 3600,
        },
        "db": {"type": "mongodb", "uri": "mongodb://localhost:27017"},
        "transform": {
            "cache": {
                "location": ".wks/cache",
                "max_size_bytes": 1073741824,
            },
            "database": "wks.transform",
            "engines": {},
        },
        "diff": {
            "engines": {
                "myers": {"enabled": True, "is_default": True},
            },
            "_router": {
                "rules": [],
                "fallback": "myers",
            },
        },
    }
    (home_dir / ".wks" / "config.json").write_text(json.dumps(config))

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
    process.stdin.write(json.dumps(request) + "\n")
    process.stdin.flush()

    # Read response
    line = process.stdout.readline()
    if not line:
        return None

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
    assert "tracked_files" in content


def test_mcp_call_monitor_check(mcp_process):
    """Test tools/call wks_monitor_check."""
    response = send_request(
        mcp_process,
        "tools/call",
        {"name": "wksm_monitor_check", "arguments": {"path": "/tmp"}},
        req_id=4,
    )

    content = json.loads(response["result"]["content"][0]["text"])
    assert "is_monitored" in content
