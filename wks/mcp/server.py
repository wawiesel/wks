import inspect
import json
import sys
from collections.abc import Callable
from typing import Any

from wks.api.config.get_package_version import get_package_version
from wks.api.config.StageResult import StageResult
from wks.api.config.WKSConfig import WKSConfig

from .discover_commands import discover_commands


def _tool_name(domain: str, cmd_name: str) -> str:
    """Build MCP tool name from domain/command pair."""
    if domain == "_root":
        return f"wksm_{cmd_name}"
    if domain == cmd_name:
        return f"wksm_{domain}"
    return f"wksm_{domain}_{cmd_name}"


def _json_type(annotation: Any) -> str:
    """Map a Python type annotation to a JSON schema type string."""
    if annotation == inspect.Parameter.empty:
        return "string"
    # Unwrap Optional / X | None
    if hasattr(annotation, "__args__") and type(None) in annotation.__args__:
        annotation = next(a for a in annotation.__args__ if a is not type(None))
    if annotation is int or (hasattr(annotation, "__origin__") and annotation.__origin__ is int):
        return "integer"
    if annotation is bool:
        return "boolean"
    if annotation is float:
        return "number"
    if annotation is dict or (hasattr(annotation, "__origin__") and annotation.__origin__ is dict):
        return "object"
    return "string"


def _schema_from_func(func: Callable) -> dict[str, Any]:
    """Generate a JSON schema from an API function's signature."""
    sig = inspect.signature(func)
    schema: dict[str, Any] = {"type": "object", "properties": {}, "required": []}
    for name, param in sig.parameters.items():
        if name in ("self", "ctx"):
            continue
        schema["properties"][name] = {"type": _json_type(param.annotation), "description": ""}
        if param.default == inspect.Parameter.empty:
            schema["required"].append(name)
    return schema


def _description_from_func(func: Callable, domain: str, cmd_name: str) -> str:
    """Extract a one-line description from a function's docstring."""
    if func.__doc__:
        return func.__doc__.split("\n")[0].strip()
    return f"{domain} {cmd_name} operation"


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
        """Build tool metadata from discovered API functions."""
        tools = {}
        for (domain, cmd_name), cmd_func in discover_commands().items():
            name = _tool_name(domain, cmd_name)
            tools[name] = {
                "description": _description_from_func(cmd_func, domain, cmd_name),
                "inputSchema": _schema_from_func(cmd_func),
            }
        return tools

    def build_registry(self) -> dict[str, Callable[[WKSConfig, dict[str, Any]], dict[str, Any]]]:
        """Build a registry of tool handlers mapped by name."""
        registry: dict[str, Callable[[WKSConfig, dict[str, Any]], dict[str, Any]]] = {}
        for (domain, cmd_name), cmd_func in discover_commands().items():
            sig = inspect.signature(cmd_func)

            def make_handler(func: Callable, sig: inspect.Signature) -> Callable:
                def handler(_config: WKSConfig, args: dict[str, Any]) -> dict[str, Any]:
                    from wks.api.config.URI import URI

                    kwargs = {}
                    for param_name, param in sig.parameters.items():
                        if param_name == "self":
                            continue
                        val = args.get(param_name)
                        if val is None and param_name == "uri":
                            val = args.get("path")
                        if val is not None:
                            if param_name == "query" and isinstance(val, dict):
                                val = json.dumps(val)
                            elif param_name == "uri" and isinstance(val, str):
                                val = URI.from_any(val)
                            kwargs[param_name] = val
                        elif param.default == inspect.Parameter.empty:
                            raise ValueError(f"Missing required argument: {param_name}")
                    result = func(**kwargs)
                    if isinstance(result, StageResult):
                        list(result.progress_callback(result))
                        return {"success": result.success, "data": result.output}
                    return {"success": True, "data": result if isinstance(result, dict) else {}}

                return handler

            name = _tool_name(domain, cmd_name)
            registry[name] = make_handler(cmd_func, sig)

        return registry

    def read_message(self) -> dict[str, Any] | None:
        """Read and decode a single JSON-RPC message from the input stream."""
        try:
            while True:
                line = self._input.readline()
                if not line:
                    return None
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
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "wks-mcp-server", "version": get_package_version()},
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
                    {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {"code": -32601, "message": f"Tool not found: {tool_name}"},
                    }
                )
                return
            try:
                registry = self.build_registry()
                if tool_name not in registry:
                    self.write_message(
                        {
                            "jsonrpc": "2.0",
                            "id": request_id,
                            "error": {"code": -32601, "message": f"Tool not implemented: {tool_name}"},
                        }
                    )
                    return
                result = registry[tool_name](WKSConfig.load(), arguments)
                self.write_message(
                    {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]},
                    }
                )
            except Exception as e:
                self.write_message(
                    {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {"code": -32000, "message": f"Tool execution failed: {e}"},
                    }
                )
        elif request_id is not None:
            self.write_message(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"},
                }
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
