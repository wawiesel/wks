"""MCP Server for WKS - auto-discovers cmd_* functions and exposes them as MCP tools."""

import inspect
import json
import sys
from collections.abc import Callable
from typing import Any

from wks.api.StageResult import StageResult
from wks.api.config.WKSConfig import WKSConfig
from wks.cli.get_typer_command_schema import get_typer_command_schema

from .discover_commands import discover_commands
from .get_app import get_app


class MCPServer:
    """Simple JSON-RPC server for MCP tools."""

    def __init__(self, *, input_stream: Any | None = None, output_stream: Any | None = None):
        self._input = input_stream or sys.stdin
        self._output = output_stream or sys.stdout
        self._lsp_mode = False
        self.tools = self.define_tools()
        self.resources = [
            {"uri": "mcp://wks/tools", "name": "wks-tools", "description": "WKS tools", "type": "tool-collection"},
        ]

    @staticmethod
    def define_tools() -> dict[str, dict[str, Any]]:
        """Build tool metadata from discovered CLI commands."""
        tools = {}
        for (domain, cmd_name), cmd_func in discover_commands().items():
            app = get_app(domain)
            if app is None:
                continue
            if domain == "config" and cmd_name == "show":
                schema = get_typer_command_schema(app, None)
                command = next((cmd for cmd in app.registered_commands if cmd.name is None), None)
            else:
                command, schema_app, schema_cmd = None, app, cmd_name
                for cmd in app.registered_commands:
                    if cmd.name == cmd_name:
                        command, schema_app, schema_cmd = cmd, app, cmd_name
                        break
                if command is None and hasattr(app, "registered_groups"):
                    for group in app.registered_groups:
                        prefix = f"{group.name}_"
                        if cmd_name.startswith(prefix) and hasattr(group, "typer_instance"):
                            sub_cmd = cmd_name[len(prefix):]
                            for cmd in group.typer_instance.registered_commands:
                                if cmd.name == sub_cmd:
                                    command, schema_app, schema_cmd = cmd, group.typer_instance, sub_cmd
                                    break
                            if command:
                                break
                if command is None:
                    continue
                schema = get_typer_command_schema(schema_app, schema_cmd)
            description = (
                command.callback.__doc__.split("\n")[0].strip()
                if (command and command.callback and command.callback.__doc__)
                else f"{domain} {cmd_name} operation"
            )
            tools[f"wksm_{domain}_{cmd_name}"] = {"description": description, "inputSchema": schema}
        return tools

    def build_registry(self) -> dict[str, Callable[[WKSConfig, dict[str, Any]], dict[str, Any]]]:
        """Build a registry of tool handlers mapped by name."""
        registry: dict[str, Callable[[WKSConfig, dict[str, Any]], dict[str, Any]]] = {}
        for (domain, cmd_name), cmd_func in discover_commands().items():
            sig = inspect.signature(cmd_func)

            def make_handler(func: Callable, sig: inspect.Signature, domain: str) -> Callable:
                def handler(config: WKSConfig, args: dict[str, Any]) -> dict[str, Any]:  # noqa: ARG001
                    kwargs = {}
                    for param_name, param in sig.parameters.items():
                        if param_name == "self":
                            continue
                        val = args.get(param_name)
                        if val is not None:
                            if param_name == "query" and isinstance(val, dict):
                                val = json.dumps(val)
                            kwargs[param_name] = val
                        elif param.default == inspect.Parameter.empty:
                            raise ValueError(f"Missing required argument: {param_name}")
                    result = func(**kwargs)
                    if isinstance(result, StageResult):
                        list(result.progress_callback(result))
                        return {"success": result.success, "data": result.output}
                    return {"success": True, "data": result if isinstance(result, dict) else {}}

                return handler

            registry[f"wksm_{domain}_{cmd_name}"] = make_handler(cmd_func, sig, domain)
        return registry

    def read_message(self) -> dict[str, Any] | None:
        """Read and decode a single JSON-RPC message from the input stream."""
        try:
            while True:
                line = self._input.readline()
                if not line:
                    return None
                # Skip blank lines (common after framed LSP payloads).
                if not line.strip():
                    continue
                if line.strip().lower().startswith("content-length"):
                    length = int(line.split(":", 1)[1].strip())
                    while True:
                        sep = self._input.readline()
                        if not sep.strip() or sep in ("\r\n", "\n", "\r"):
                            break
                    self._lsp_mode = True
                    return json.loads(self._input.read(length))
                return json.loads(line)
        except Exception:
            return None

    def write_message(self, message: dict[str, Any]) -> None:
        """Write a JSON-RPC response to the output stream."""
        payload = json.dumps(message)
        if self._lsp_mode:
            encoded = payload.encode("utf-8")
            self._output.write(f"Content-Length: {len(encoded)}\r\n\r\n{payload}")
        else:
            self._output.write(payload)
        self._output.write("\n")
        self._output.flush()

    def handle_request(self, message: dict[str, Any]) -> None:
        """Handle a single JSON-RPC request."""
        request_id, method, params = message.get("id"), message.get("method"), message.get("params", {})
        if method == "initialize":
            self.write_message(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "serverInfo": {"name": "wks-mcp-server", "version": "1.0.0"},
                    },
                }
            )
        elif method == "tools/list":
            self.write_message(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "tools": [
                            {"name": name, "description": info["description"], "inputSchema": info["inputSchema"]}
                            for name, info in self.tools.items()
                        ]
                    },
                }
            )
        elif method == "resources/list":
            self.write_message({"jsonrpc": "2.0", "id": request_id, "result": {"resources": self.resources}})
        elif method == "tools/call":
            tool_name, arguments = params.get("name"), params.get("arguments", {})
            if tool_name not in self.tools:
                self.write_message(
                    {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": f"Tool not found: {tool_name}"}}
                )
                return
            try:
                registry = self.build_registry()
                if tool_name not in registry:
                    self.write_message(
                        {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": f"Tool not implemented: {tool_name}"}}
                    )
                    return
                result = registry[tool_name](WKSConfig.load(), arguments)
                self.write_message(
                    {"jsonrpc": "2.0", "id": request_id, "result": {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}}
                )
            except Exception as e:
                self.write_message(
                    {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32000, "message": f"Tool execution failed: {e}"}}
                )
        elif request_id is not None:
            self.write_message(
                {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}
            )

    def run(self) -> None:
        """Run the request loop until EOF."""
        while True:
            message = self.read_message()
            if message is None:
                break
            self.handle_request(message)


if __name__ == "__main__":
    from .main import main

    main()
