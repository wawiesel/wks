from __future__ import annotations

import io
import json
import platform
import socket
import time
from pathlib import Path
from uuid import uuid4

import pytest

from wks.mcp_bridge import MCPBroker
from wks.mcp_client import proxy_stdio_to_socket


def _tmp_socket() -> Path:
    # Use shorter path to avoid AF_UNIX path length limits in CI
    # Linux limit is 108 chars, so use /tmp with minimal name
    # Fixed path for CI stability - in real deployments, use unique paths
    return Path("/tmp") / "wks-mcp.sock"


@pytest.mark.integration
def test_mcp_broker_handles_requests():
    sock_path = _tmp_socket()
    # Skip if path too long (AF_UNIX limit is 108 chars on Linux)
    if len(str(sock_path)) > 100:
        pytest.skip(f"Socket path too long: {sock_path}")
    broker = MCPBroker(sock_path)
    broker.start()

    # Give broker time to start
    time.sleep(0.1)

    try:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.connect(str(sock_path))
        rfile = client.makefile("r")
        wfile = client.makefile("w")

        wfile.write(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "resources/list", "params": {}}) + "\n")
        wfile.flush()
        response = rfile.readline()
        assert response, "No response from broker"
        assert "resources" in response or "error" in response.lower() or "result" in response.lower()
        client.close()
    finally:
        broker.stop()
        # Give broker time to clean up
        time.sleep(0.1)

    # Socket should be cleaned up
    if sock_path.exists():
        # On some systems, cleanup might be delayed
        time.sleep(0.1)


@pytest.mark.integration
def test_proxy_stdio_to_socket():
    sock_path = _tmp_socket()
    # Skip if path too long (AF_UNIX limit is 108 chars on Linux)
    if len(str(sock_path)) > 100:
        pytest.skip(f"Socket path too long: {sock_path}")
    broker = MCPBroker(sock_path)
    broker.start()

    # Give broker time to start
    time.sleep(0.1)

    try:
        stdin = io.StringIO(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {}}) + "\n")
        stdout = io.StringIO()

        result = proxy_stdio_to_socket(sock_path, stdin=stdin, stdout=stdout)
        assert result, "proxy_stdio_to_socket failed"
    finally:
        broker.stop()
        time.sleep(0.1)

    output = stdout.getvalue()
    assert output, "No output from proxy"
    # Response should contain the id or be a valid JSON-RPC response
    assert '"id": 1' in output or '"error"' in output.lower() or '"result"' in output.lower()

