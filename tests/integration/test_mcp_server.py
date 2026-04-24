import io
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest

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


def make_server():
    output = io.StringIO()
    return server_mod.MCPServer(input_stream=io.StringIO(), output_stream=output), output


def call_request(server, output, request):
    server.handle_request(request)
    return json.loads(output.getvalue())


def test_handle_initialize_writes_response():
    server, output = make_server()
    response = call_request(server, output, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})

    assert response["id"] == 1
    assert response["result"]["serverInfo"]["name"] == "wks-mcp-server"
    assert "resources" in response["result"]["capabilities"]


def test_tools_and_resources_listing():
    server, output = make_server()
    server.tools = {"tool_a": {"description": "A", "inputSchema": {"type": "object"}}}
    server.resources = [{"uri": "mcp://wks/tools", "name": "tools", "description": "d", "type": "tool-collection"}]

    tools_response = call_request(server, output, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    assert tools_response["result"]["tools"][0]["name"] == "tool_a"

    output.truncate(0)
    output.seek(0)
    resources_response = call_request(
        server, output, {"jsonrpc": "2.0", "id": 3, "method": "resources/list", "params": {}}
    )
    assert resources_response["result"]["resources"][0]["uri"] == "mcp://wks/tools"


def test_define_tools_enrich_search_and_cat_schemas():
    tools = server_mod.MCPServer.define_tools()
    search_schema = tools["search"]["inputSchema"]
    cat_schema = tools["cat"]["inputSchema"]

    assert search_schema["additionalProperties"] is False
    assert search_schema["properties"]["query"]["minLength"] == 1
    assert search_schema["properties"]["k"]["default"] == 10
    assert search_schema["properties"]["k"]["minimum"] == 1
    assert "anyOf" not in search_schema

    assert cat_schema["additionalProperties"] is False
    assert cat_schema["required"] == ["target"]
    assert cat_schema["properties"]["target"]["description"] == "Checksum, cached artifact, or filesystem path to read."
    assert (
        cat_schema["properties"]["output_path"]["description"] == "Optional file path to write the rendered content to."
    )
    assert (
        cat_schema["properties"]["engine"]["description"]
        == "Optional transform engine to run before returning content."
    )


def test_define_tools_use_object_schemas_without_top_level_combinators():
    for tool in server_mod.MCPServer.define_tools().values():
        schema = tool["inputSchema"]
        assert schema["type"] == "object"
        for keyword in ("oneOf", "anyOf", "allOf", "enum", "not"):
            assert keyword not in schema


def test_resources_read_returns_tools_document():
    server, output = make_server()
    server.tools = {
        "search": {"description": "Search docs", "inputSchema": {"type": "object"}},
        "cat": {"description": "Read content", "inputSchema": {"type": "object"}},
    }

    response = call_request(
        server,
        output,
        {"jsonrpc": "2.0", "id": 30, "method": "resources/read", "params": {"uri": "mcp://wks/tools"}},
    )
    contents = response["result"]["contents"]
    document = json.loads(contents[0]["text"])

    assert contents[0]["uri"] == "mcp://wks/tools"
    assert contents[0]["mimeType"] == "application/json"
    assert document["server"] == "wks"
    assert document["preferred_workflow"] == {"search": "search", "read": "cat"}
    assert [tool["name"] for tool in document["tools"]] == ["cat", "search"]


@pytest.mark.parametrize(
    ("method", "params", "code", "message"),
    [
        ("resources/read", {"uri": "mcp://wks/missing"}, -32601, "Resource not found"),
        ("resources/templates/list", {}, None, None),
        ("unknown", None, -32601, None),
    ],
)
def test_request_error_and_empty_paths(method, params, code, message):
    server, output = make_server()
    response = call_request(
        server,
        output,
        {"jsonrpc": "2.0", "id": 31, "method": method, **({"params": params} if params is not None else {})},
    )

    if method == "resources/templates/list":
        assert response["result"]["resourceTemplates"] == []
        return

    assert response["error"]["code"] == code
    if message is not None:
        assert message in response["error"]["message"]


@pytest.mark.parametrize(
    ("tool_name", "registry", "arguments", "expected_code", "expected_message"),
    [
        ("missing", {}, {}, -32601, None),
        ("dummy", {}, {}, -32601, "Tool not implemented"),
        ("boom", {"boom": lambda _cfg, _args: (_ for _ in ()).throw(RuntimeError("fail"))}, {}, None, "fail"),
    ],
)
def test_tools_call_error_paths(monkeypatch, tool_name, registry, arguments, expected_code, expected_message):
    server, output = make_server()
    server.tools = {tool_name: {"description": "x", "inputSchema": {}}} if tool_name != "missing" else {}
    monkeypatch.setattr(server, "build_registry", lambda: registry)
    monkeypatch.setattr(WKSConfig, "load", classmethod(lambda cls: object()))

    response = call_request(
        server,
        output,
        {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": tool_name, "arguments": arguments}},
    )

    if expected_code is not None:
        assert response["error"]["code"] == expected_code
    if expected_message is not None:
        assert expected_message in response["error"]["message"]


def test_tools_call_happy_path(monkeypatch):
    server, output = make_server()
    server.tools = {"dummy_run": {"description": "x", "inputSchema": {}}}
    monkeypatch.setattr(
        server, "build_registry", lambda: {"dummy_run": lambda cfg, args: {"success": True, "data": args}}
    )
    monkeypatch.setattr(WKSConfig, "load", classmethod(lambda cls: object()))

    response = call_request(
        server,
        output,
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "dummy_run", "arguments": {"a": 1}}},
    )
    content = json.loads(response["result"]["content"][0]["text"])
    assert content["data"]["a"] == 1


def test_build_registry_handles_stage_and_plain_results(monkeypatch):
    captured: dict[str, Any] = {}

    class Dummy:
        def method(self, value: str):
            return {"echo": value}

    def stage_func(section: str):
        return StageResult(announce="a", progress_callback=_progress, output={"section": section}, success=True)

    def query_func(query):
        captured["query"] = query
        return {"seen": query}

    monkeypatch.setattr(
        server_mod,
        "discover_commands",
        lambda: {
            ("config", "show"): stage_func,
            ("monitor", "check"): query_func,
            ("database", "reset"): lambda: "ok",
            ("dummy", "call"): Dummy().method,
        },
    )

    registry = make_server()[0].build_registry()
    assert registry["config_show"](None, {"section": ""})["data"]["section"] == ""
    assert registry["database_reset"](None, {}) == {"success": True, "data": {}}

    query_result = registry["monitor_check"](None, {"query": {"a": 1}})
    assert captured["query"] == json.dumps({"a": 1})
    assert query_result["data"]["seen"] == json.dumps({"a": 1})
    assert registry["dummy_call"](None, {"value": "ok"})["data"]["echo"] == "ok"


def test_call_tool_success_and_failure(monkeypatch):
    missing = call_tool("nope", {})
    assert missing["success"] is False
    assert "Tool not found" in missing["error"]

    with (
        patch.object(
            server_mod.MCPServer,
            "build_registry",
            lambda self: {"custom": lambda cfg, args: {"success": True, "data": args}},
        ),
        patch.object(WKSConfig, "load", return_value=None),
    ):
        result = call_tool("custom", {"x": 1})
        assert result["success"] is True
        assert result["data"]["x"] == 1


def test_main_handles_keyboardinterrupt_and_error():
    with patch.object(server_mod.MCPServer, "run", side_effect=KeyboardInterrupt), patch("sys.exit") as mock_exit:
        mcp_main()
        mock_exit.assert_called_once_with(0)

    with patch.object(server_mod.MCPServer, "run", side_effect=RuntimeError("boom")), patch("sys.exit") as mock_exit:
        mcp_main()
        mock_exit.assert_called_once_with(1)


def test_discover_commands_and_define_tools_cover_branches(monkeypatch):
    assert discover_commands()

    monkeypatch.setattr(server_mod, "discover_commands", lambda: {("dummy", "missing"): lambda: None})
    assert server_mod.MCPServer.define_tools()["dummy_missing"]["inputSchema"]["type"] == "object"


def test_build_registry_handles_self_param(monkeypatch):
    monkeypatch.setattr(
        server_mod, "discover_commands", lambda: {("dummy", "echo"): lambda self=None, value=None: {"echo": value}}
    )
    registry = make_server()[0].build_registry()
    assert registry["dummy_echo"](None, {"value": "hi"})["data"]["echo"] == "hi"


def test_build_registry_coerces_cat_arguments(wks_home):
    watch_dir = Path(wks_home).parent / "watched"
    watch_dir.mkdir(parents=True, exist_ok=True)

    test_file = watch_dir / "test.txt"
    test_file.write_text("Hello MCP Cat", encoding="utf-8")
    output_file = watch_dir / "output.md"
    registry = make_server()[0].build_registry()

    result_path = registry["cat"](None, {"target": str(test_file), "output_path": str(output_file)})
    result_uri = registry["cat"](None, {"target": str(URI.from_path(test_file))})

    assert result_path["success"] is True
    assert output_file.read_text(encoding="utf-8") == "Hello MCP Cat"
    assert result_uri["success"] is True
    assert result_uri["data"]["content"] == "Hello MCP Cat"


def test_read_message_lsp_and_eof():
    body = json.dumps({"id": 1, "method": "initialize", "params": {}})
    server = server_mod.MCPServer(
        input_stream=io.StringIO(f"Content-Length: {len(body)}\r\n\r\n{body}"),
        output_stream=io.StringIO(),
    )

    msg = server.read_message()
    assert msg is not None
    assert msg["method"] == "initialize"
    assert server.read_message() is None


def test_run_processes_messages_and_stops():
    output = io.StringIO()
    server = server_mod.MCPServer(
        input_stream=io.StringIO('{"jsonrpc": "2.0", "id": 9, "method": "initialize", "params": {}}\n'),
        output_stream=output,
    )
    server.run()
    assert "wks-mcp-server" in output.getvalue()


def test_discover_commands_handles_none_command_and_group(monkeypatch, tmp_path):
    fake_cli_file = tmp_path / "dummy.py"
    fake_cli_file.write_text("# dummy cli")
    cli_root = Path(discover_commands_mod.__file__).parent.parent / "cli"

    def fake_glob(self, pattern):
        return [fake_cli_file] if self == cli_root else []

    class DummyCmd:
        def __init__(self, name):
            self.name = name
            self.callback = lambda: None

    class DummyApp:
        def __init__(self):
            self.registered_commands = [DummyCmd(None)]
            self.registered_groups = [type("Group", (), {})()]

    monkeypatch.setattr(Path, "glob", fake_glob)
    monkeypatch.setattr("importlib.import_module", lambda name: SimpleNamespace(dummy_app=DummyApp()))
    assert discover_commands() == {}
