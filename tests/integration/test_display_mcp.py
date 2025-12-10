import io
import json

from wks.mcp.server import MCPServer


def test_mcp_server_handles_content_length_and_plain_messages():
    """Server run loop should parse both framed and plain JSON requests."""
    payload1 = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
    raw1 = json.dumps(payload1)
    framed = f"Content-Length: {len(raw1)}\r\n\r\n{raw1}"

    payload2 = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
    plain = json.dumps(payload2)

    input_stream = io.StringIO(f"{framed}\n{plain}\n")
    output_stream = io.StringIO()
    server = MCPServer(input_stream=input_stream, output_stream=output_stream)

    server.run()
    output = output_stream.getvalue()
    # Both responses should be present; LSP mode triggers Content-Length header
    assert "wks-mcp-server" in output
    assert "tools" in output
    assert "Content-Length" in output


def test_mcp_server_ignores_invalid_json():
    """Invalid input should stop processing without raising."""
    input_stream = io.StringIO("not json\n")
    output_stream = io.StringIO()
    server = MCPServer(input_stream=input_stream, output_stream=output_stream)
    server.run()
    # No output produced, but run should complete without error
    assert output_stream.getvalue() == ""
