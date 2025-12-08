"""MCP Server for WKS - Auto-discovers cmd_* functions and exposes as MCP tools."""

import importlib
import inspect
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from wks.api.StageResult import StageResult
from wks.api.get_typer_command_schema import get_typer_command_schema
from wks.api.config.WKSConfig import WKSConfig


def _discover() -> dict[tuple[str, str], Callable]:
    """Auto-discover all cmd_* functions from non-underscore directories in wks.api."""
    commands: dict[tuple[str, str], Callable] = {}
    api_path = Path(__file__).parent.parent / "api"
    for domain_dir in api_path.iterdir():
        if not domain_dir.is_dir() or domain_dir.name.startswith("_"):
            continue
        for cmd_file in domain_dir.glob("cmd_*.py"):
            cmd_name = cmd_file.stem[4:]
            try:
                module = importlib.import_module(f"wks.api.{domain_dir.name}.{cmd_file.stem}")
                func = getattr(module, f"cmd_{cmd_name}", None)
                if callable(func):
                    commands[(domain_dir.name, cmd_name)] = func
            except Exception:
                continue
    return commands


def _get_app(domain: str) -> Any:
    """Auto-discover Typer app for a domain by trying common naming patterns."""
    # Try common app name patterns: {domain}_app, db_app (special case), {domain}app, app
    patterns = [f"{domain}_app", "db_app" if domain == "database" else None, f"{domain}app", "app"]
    for pattern in patterns:
        if pattern is None:
            continue
        try:
            module = importlib.import_module(f"wks.api.{domain}.app")
            app = getattr(module, pattern, None)
            if app is not None:
                return app
        except Exception:
            continue
    return None


class MCPServer:
    def __init__(self, *, input_stream: Any | None = None, output_stream: Any | None = None):
        self._input = input_stream or sys.stdin
        self._output = output_stream or sys.stdout
        self._lsp_mode = False
        self.tools = self._define_tools()
        self.resources = [{"uri": "mcp://wks/tools", "name": "wks-tools", "description": "WKS tools", "type": "tool-collection"}]

    @staticmethod
    def _define_tools() -> dict[str, dict[str, Any]]:
        tools = {}
        for (domain, cmd_name), cmd_func in _discover().items():
            app = _get_app(domain)
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
            description = (command.callback.__doc__.split("\n")[0].strip() if (command and command.callback and command.callback.__doc__) else f"{domain} {cmd_name} operation")
            tools[f"wksm_{domain}_{cmd_name}"] = {"description": description, "inputSchema": schema}
        return tools

    def _build_registry(self) -> dict[str, Callable[[WKSConfig, dict[str, Any]], dict[str, Any]]]:
        registry: dict[str, Callable[[WKSConfig, dict[str, Any]], dict[str, Any]]] = {}
        for (domain, cmd_name), cmd_func in _discover().items():
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
                            kwargs[param_name] = "" if param_name == "section" and domain == "config" else args.get(param_name, "")
                    result = func(**kwargs)
                    if isinstance(result, StageResult):
                        # Execute progress callback
                        list(result.progress_callback(result))
                        return {"success": result.success, "data": result.output}
                    return {"success": True, "data": result if isinstance(result, dict) else {}}

                return handler

            registry[f"wksm_{domain}_{cmd_name}"] = make_handler(cmd_func, sig, domain)
        return registry

    def _read_message(self) -> dict[str, Any] | None:
        try:
            line = self._input.readline()
            if not line:
                return None
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

    def _write_message(self, message: dict[str, Any]) -> None:
        payload = json.dumps(message)
        if self._lsp_mode:
            encoded = payload.encode("utf-8")
            self._output.write(f"Content-Length: {len(encoded)}\r\n\r\n{payload}")
        else:
            self._output.write(payload)
        self._output.write("\n")
        self._output.flush()

    def _handle_request(self, message: dict[str, Any]) -> None:
        request_id, method, params = message.get("id"), message.get("method"), message.get("params", {})
        if method == "initialize":
            self._write_message({"jsonrpc": "2.0", "id": request_id, "result": {"protocolVersion": "2024-11-05", "capabilities": {}, "serverInfo": {"name": "wks-mcp-server", "version": "1.0.0"}}})
        elif method == "tools/list":
            self._write_message({"jsonrpc": "2.0",
                                 "id": request_id,
                                 "result": {"tools": [{"name": name,
                                                       "description": info["description"],
                                                       "inputSchema": info["inputSchema"]} for name,
                                                      info in self.tools.items()]}})
        elif method == "resources/list":
            self._write_message({"jsonrpc": "2.0", "id": request_id, "result": {"resources": self.resources}})
        elif method == "tools/call":
            tool_name, arguments = params.get("name"), params.get("arguments", {})
            if tool_name not in self.tools:
                self._write_message({"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": f"Tool not found: {tool_name}"}})
                return
            try:
                registry = self._build_registry()
                if tool_name not in registry:
                    self._write_message({"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": f"Tool not implemented: {tool_name}"}})
                    return
                result = registry[tool_name](WKSConfig.load(), arguments)
                self._write_message({"jsonrpc": "2.0", "id": request_id, "result": {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}})
            except Exception as e:
                self._write_message({"jsonrpc": "2.0", "id": request_id, "error": {"code": -32000, "message": f"Tool execution failed: {e}"}})
        elif request_id is not None:
            self._write_message({"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": f"Method not found: {method}"}})

    def run(self) -> None:
        while True:
            message = self._read_message()
            if message is None:
                break
            self._handle_request(message)


def call_tool(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    server = MCPServer()
    registry = server._build_registry()
    if tool_name not in registry:
        return {"success": False, "data": {}, "error": f"Tool not found: {tool_name}"}
    return registry[tool_name](WKSConfig.load(), arguments)


def main() -> None:
    server = MCPServer()
    try:
        server.run()
    except KeyboardInterrupt:
        sys.stderr.write("\nMCP Server stopped.\n")
        sys.exit(0)
    except Exception as e:
        sys.stderr.write(f"MCP Server error: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
