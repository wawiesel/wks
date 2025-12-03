from __future__ import annotations

import io
import json
import socket
from pathlib import Path

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

    try:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.connect(str(sock_path))
        rfile = client.makefile("r")
        wfile = client.makefile("w")

        wfile.write(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "resources/list", "params": {}}) + "\n")
        wfile.flush()
        response = rfile.readline()
        assert "resources" in response
        client.close()
    finally:
        broker.stop()

    assert not sock_path.exists()


@pytest.mark.integration
def test_proxy_stdio_to_socket():
    sock_path = _tmp_socket()
    # Skip if path too long (AF_UNIX limit is 108 chars on Linux)
    if len(str(sock_path)) > 100:
        pytest.skip(f"Socket path too long: {sock_path}")
    broker = MCPBroker(sock_path)
    broker.start()

    try:
        stdin = io.StringIO(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {}}) + "\n")
        stdout = io.StringIO()

        assert proxy_stdio_to_socket(sock_path, stdin=stdin, stdout=stdout)
    finally:
        broker.stop()

    output = stdout.getvalue()
    assert '"id": 1' in output
