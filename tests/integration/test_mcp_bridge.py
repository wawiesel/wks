from __future__ import annotations

import io
import json
import socket
from pathlib import Path
from uuid import uuid4

import pytest

from wks.mcp_bridge import MCPBroker
from wks.mcp_client import proxy_stdio_to_socket


def _tmp_socket() -> Path:
    return Path("/tmp") / f"wks-mcp-test-{uuid4().hex}.sock"


@pytest.mark.integration
def test_mcp_broker_handles_requests():
    sock_path = _tmp_socket()
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

