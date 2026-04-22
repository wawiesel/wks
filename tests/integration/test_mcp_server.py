"""Integration tests for MCPServer request handling."""

import io
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import wks.mcp.server as server_mod
from wks.api.config.StageResult import StageResult
from wks.api.config.URI import URI
from wks.api.config.WKSConfig import WKSConfig
from wks.mcp import discover_commands as discover_commands_mod
from wks.mcp.call_tool import call_tool
from wks.mcp.discover_commands import discover_commands
from wks.mcp.main import main as mcp_main


def _progress(result: StageResult):
    yield (1.0, "done")


def _server_with_streams():
    output = io.StringIO()
    server = server_mod.MCPServer(input_stream=io.StringIO(), output_stream=output)
    return server, output


def test_handle_initialize_writes_response():
    server, output = _server_with_streams()
    server.handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})

    response = json.loads(output.getvalue())
    assert response["id"] == 1
    assert response["result"]["serverInfo"]["name"] == "wks-mcp-server"
    assert "resources" in response["result"]["capabilities"]


def test_tools_and_resources_listing():
    server, output = _server_with_streams()
    server.tools = {
        "tool_a": {"description": "A", "inputSchema": {"type": "object"}},
    }
    server.resources = [{"uri": "mcp://wks/tools", "name": "tools", "description": "d", "type": "tool-collection"}]

    server.handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    tools_response = json.loads(output.getvalue())
    assert tools_response["result"]["tools"][0]["name"] == "tool_a"

    output.truncate(0)
    output.seek(0)
    server.handle_request({"jsonrpc": "2.0", "id": 3, "method": "resources/list", "params": {}})
    resources_response = json.loads(output.getvalue())
    assert resources_response["result"]["resources"][0]["uri"] == "mcp://wks/tools"


def test_define_tools_enriches_search_schema():
    tools = server_mod.MCPServer.define_tools()
    schema = tools["search"]["inputSchema"]

    assert schema["additionalProperties"] is False
    assert (
        schema["properties"]["query"]["description"]
        == "Text query to search for. Provide this for normal text retrieval."
    )
    assert schema["properties"]["query"]["minLength"] == 1
    assert schema["properties"]["k"]["description"] == "Maximum number of ranked hits to return."
    assert schema["properties"]["k"]["default"] == 10
    assert schema["properties"]["k"]["minimum"] == 1
    assert (
        schema["properties"]["strategy"]["description"]
        == "Optional named search strategy. Mutually exclusive with `index`."
    )
    assert schema["anyOf"] == [{"required": ["query"]}, {"required": ["query_image"]}]


def test_define_tools_enriches_cat_schema():
    tools = server_mod.MCPServer.define_tools()
    schema = tools["cat"]["inputSchema"]

    assert schema["additionalProperties"] is False
    assert schema["required"] == ["target"]
    assert schema["properties"]["target"]["description"] == "Checksum, cached artifact, or filesystem path to read."
    assert schema["properties"]["output_path"]["description"] == "Optional file path to write the rendered content to."
    assert schema["properties"]["engine"]["description"] == "Optional transform engine to run before returning content."


def test_resources_read_returns_tools_document():
    server, output = _server_with_streams()
    server.tools = {
        "search": {"description": "Search docs", "inputSchema": {"type": "object"}},
        "cat": {"description": "Read content", "inputSchema": {"type": "object"}},
    }

    server.handle_request(
        {"jsonrpc": "2.0", "id": 30, "method": "resources/read", "params": {"uri": "mcp://wks/tools"}}
    )
    response = json.loads(output.getvalue())
    contents = response["result"]["contents"]
    assert contents[0]["uri"] == "mcp://wks/tools"
    assert contents[0]["mimeType"] == "application/json"
    document = json.loads(contents[0]["text"])
    assert document["server"] == "wks"
    assert document["preferred_workflow"] == {"search": "search", "read": "cat"}
    assert [tool["name"] for tool in document["tools"]] == ["cat", "search"]


def test_resources_read_missing_resource():
    server, output = _server_with_streams()

    server.handle_request(
        {"jsonrpc": "2.0", "id": 31, "method": "resources/read", "params": {"uri": "mcp://wks/missing"}}
    )
    response = json.loads(output.getvalue())
    assert response["error"]["code"] == -32601
    assert "Resource not found" in response["error"]["message"]


def test_resource_templates_list_returns_empty():
    server, output = _server_with_streams()

    server.handle_request({"jsonrpc": "2.0", "id": 32, "method": "resources/templates/list", "params": {}})
    response = json.loads(output.getvalue())
    assert response["result"]["resourceTemplates"] == []


def test_tools_call_happy_path(monkeypatch):
    server, output = _server_with_streams()
    server.tools = {"dummy_run": {"description": "x", "inputSchema": {}}}
    monkeypatch.setattr(
        server, "build_registry", lambda: {"dummy_run": lambda cfg, args: {"success": True, "data": args}}
    )
    monkeypatch.setattr(WKSConfig, "load", classmethod(lambda cls: object()))

    server.handle_request(
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "dummy_run", "arguments": {"a": 1}}}
    )
    response = json.loads(output.getvalue())
    content = json.loads(response["result"]["content"][0]["text"])
    assert content["data"]["a"] == 1


def test_tools_call_missing_tool(monkeypatch):
    server, output = _server_with_streams()
    server.tools = {}

    server.handle_request(
        {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "missing", "arguments": {}}}
    )
    response = json.loads(output.getvalue())
    assert response["error"]["code"] == -32601


def test_tools_call_not_implemented(monkeypatch):
    server, output = _server_with_streams()
    server.tools = {"dummy": {"description": "x", "inputSchema": {}}}
    monkeypatch.setattr(server, "build_registry", lambda: {})

    server.handle_request(
        {"jsonrpc": "2.0", "id": 6, "method": "tools/call", "params": {"name": "dummy", "arguments": {}}}
    )
    response = json.loads(output.getvalue())
    assert "Tool not implemented" in response["error"]["message"]


def test_tools_call_exception(monkeypatch):
    server, output = _server_with_streams()
    server.tools = {"boom": {"description": "x", "inputSchema": {}}}

    def boom(_cfg, _args):
        raise RuntimeError("fail")

    monkeypatch.setattr(server, "build_registry", lambda: {"boom": boom})
    monkeypatch.setattr(WKSConfig, "load", classmethod(lambda cls: object()))

    server.handle_request(
        {"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": "boom", "arguments": {}}}
    )
    response = json.loads(output.getvalue())
    assert "fail" in response["error"]["message"]


def test_handle_unknown_method():
    server, output = _server_with_streams()
    server.handle_request({"jsonrpc": "2.0", "id": 8, "method": "unknown"})
    response = json.loads(output.getvalue())
    assert response["error"]["code"] == -32601


def testbuild_registry_handles_stage_and_plain_results(monkeypatch):
    captured: dict[str, Any] = {}

    class Dummy:
        def method(self, value: str):
            return {"echo": value}

    def stage_func(section: str):
        result = StageResult(announce="a", progress_callback=_progress, output={"section": section}, success=True)
        return result

    def query_func(query):
        captured["query"] = query
        return {"seen": query}

    def text_func():  # returns non-dict
        return "ok"

    monkeypatch.setattr(
        server_mod,
        "discover_commands",
        lambda: {
            ("config", "show"): stage_func,
            ("monitor", "check"): query_func,
            ("database", "reset"): text_func,
            ("dummy", "call"): Dummy().method,
        },
    )
    server = server_mod.MCPServer(input_stream=io.StringIO(), output_stream=io.StringIO())
    registry = server.build_registry()

    # StageResult path with missing required param falls back to empty string for config section
    result_stage = registry["config_show"](None, {})  # type: ignore
    assert result_stage["success"] is True
    assert result_stage["data"]["section"] == ""

    # Query dict should be JSON encoded
    result_query = registry["monitor_check"](None, {"query": {"a": 1}})  # type: ignore
    assert captured["query"] == json.dumps({"a": 1})
    assert result_query["data"]["seen"] == json.dumps({"a": 1})

    # Non-dict return produces empty data
    result_text = registry["database_reset"](None, {})  # type: ignore
    assert result_text == {"success": True, "data": {}}

    result_self = registry["dummy_call"](None, {"value": "ok"})  # type: ignore
    assert result_self["data"]["echo"] == "ok"


def test_call_tool_success_and_failure(monkeypatch):
    # Failure path: tool not found
    missing = call_tool("nope", {})
    assert missing["success"] is False
    assert "Tool not found" in missing["error"]

    # Success path via patched registry
    def fakebuild_registry(self):
        return {"custom": lambda cfg, args: {"success": True, "data": args}}

    with (
        patch.object(server_mod.MCPServer, "build_registry", fakebuild_registry),
        patch.object(WKSConfig, "load", return_value=None),
    ):
        result = call_tool("custom", {"x": 1})
        assert result["success"] is True
        assert result["data"]["x"] == 1


def test_main_handles_keyboardinterrupt_and_error(monkeypatch):
    # KeyboardInterrupt -> exit code 0
    with (
        patch.object(server_mod.MCPServer, "run", side_effect=KeyboardInterrupt),
        patch("sys.exit") as mock_exit,
    ):
        mcp_main()
        mock_exit.assert_called_once_with(0)

    # RuntimeError -> exit code 1
    with (
        patch.object(server_mod.MCPServer, "run", side_effect=RuntimeError("boom")),
        patch("sys.exit") as mock_exit,
    ):
        mcp_main()
        mock_exit.assert_called_once_with(1)


def testdiscover_commands_and_define_tools_cover_branches(monkeypatch):
    discovered = discover_commands()
    assert discovered  # should find at least one command from real CLI

    class DummyApp:
        def __init__(self):
            self.registered_commands: list[Any] = []
            self.registered_groups: list[Any] = []

    # Force define_tools to hit the "command is None" continue branch
    monkeypatch.setattr(server_mod, "discover_commands", lambda: {("dummy", "missing"): lambda: None})
    monkeypatch.setattr(server_mod, "get_app", lambda domain: DummyApp())
    tools = server_mod.MCPServer.define_tools()
    assert "dummy_missing" not in tools


def testbuild_registry_handles_self_param(monkeypatch):
    def func_with_self(self=None, value: str | None = None):
        return {"echo": value}

    monkeypatch.setattr(server_mod, "discover_commands", lambda: {("dummy", "echo"): func_with_self})
    server = server_mod.MCPServer(input_stream=io.StringIO(), output_stream=io.StringIO())
    registry = server.build_registry()
    result = registry["dummy_echo"](None, {"value": "hi"})  # type: ignore
    assert result is not None
    assert result["data"]["echo"] == "hi"


def testbuild_registry_coerces_path_arguments_for_cat(wks_home):
    watch_dir = Path(wks_home).parent / "watched"
    watch_dir.mkdir(parents=True, exist_ok=True)

    test_file = watch_dir / "test.txt"
    test_file.write_text("Hello MCP Cat", encoding="utf-8")
    output_file = watch_dir / "output.md"

    server = server_mod.MCPServer(input_stream=io.StringIO(), output_stream=io.StringIO())
    registry = server.build_registry()

    result = registry["cat"](None, {"target": str(test_file), "output_path": str(output_file)})  # type: ignore

    assert result["success"] is True
    assert output_file.exists()
    assert output_file.read_text(encoding="utf-8") == "Hello MCP Cat"


def testbuild_registry_accepts_file_uri_target_for_cat(wks_home):
    watch_dir = Path(wks_home).parent / "watched"
    watch_dir.mkdir(parents=True, exist_ok=True)

    test_file = watch_dir / "test-uri.txt"
    test_file.write_text("Hello MCP URI Cat", encoding="utf-8")

    server = server_mod.MCPServer(input_stream=io.StringIO(), output_stream=io.StringIO())
    registry = server.build_registry()

    result = registry["cat"](None, {"target": str(URI.from_path(test_file))})  # type: ignore

    assert result["success"] is True
    assert result["data"]["content"] == "Hello MCP URI Cat"


def testread_message_lsp_and_eof():
    body = json.dumps({"id": 1, "method": "initialize", "params": {}})
    input_stream = io.StringIO(f"Content-Length: {len(body)}\r\n\r\n{body}")
    server = server_mod.MCPServer(input_stream=input_stream, output_stream=io.StringIO())

    msg = server.read_message()
    assert msg is not None
    assert msg["method"] == "initialize"
    assert server.read_message() is None  # EOF path


def test_run_processes_messages_and_stops():
    stream = io.StringIO('{"jsonrpc": "2.0", "id": 9, "method": "initialize", "params": {}}\n')
    output = io.StringIO()
    server = server_mod.MCPServer(input_stream=stream, output_stream=output)
    server.run()
    assert "wks-mcp-server" in output.getvalue()


def testdiscover_commands_handles_none_command_and_group(monkeypatch, tmp_path):
    fake_cli_file = tmp_path / "dummy.py"
    fake_cli_file.write_text("# dummy cli")

    from pathlib import Path

    cli_root = Path(discover_commands_mod.__file__).parent.parent / "cli"

    def fake_glob(self, pattern):
        if self == cli_root:
            return [fake_cli_file]
        return []

    class DummyCmd:
        def __init__(self, name):
            self.name = name
            self.callback = lambda: None

    class DummyApp:
        def __init__(self):
            self.registered_commands = [DummyCmd(None)]
            self.registered_groups = [type("Group", (), {})()]

    import importlib

    module = SimpleNamespace(dummy_app=DummyApp())
    monkeypatch.setattr(Path, "glob", fake_glob)
    monkeypatch.setattr(importlib, "import_module", lambda name: module)

    assert discover_commands() == {}
