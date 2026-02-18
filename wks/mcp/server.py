import inspect
import json
import sys
from collections.abc import Callable
from typing import Any

from wks.api.config.get_package_version import get_package_version
from wks.api.config.StageResult import StageResult
from wks.api.config.WKSConfig import WKSConfig
from wks.cli._get_typer_command_schema import get_typer_command_schema

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
    def _find_command_in_app(app: Any, cmd_name: str) -> tuple[Any, Any, str] | None:
        """Find command in app's registered commands."""
        for cmd in app.registered_commands:
            if cmd.name == cmd_name:
                return cmd, app, cmd_name
        return None

    @staticmethod
    def _find_command_in_groups(app: Any, cmd_name: str) -> tuple[Any, Any, str] | None:
        """Find command in app's registered groups."""
        if not hasattr(app, "registered_groups"):
            return None
        for group in app.registered_groups:
            prefix = f"{group.name}_"
            if cmd_name.startswith(prefix) and hasattr(group, "typer_instance"):
                sub_cmd = cmd_name[len(prefix) :]
                for cmd in group.typer_instance.registered_commands:
                    if cmd.name == sub_cmd:
                        return cmd, group.typer_instance, sub_cmd
        return None

    @staticmethod
    def _get_command_and_schema(domain: str, cmd_name: str, app: Any) -> tuple[Any, dict[str, Any]] | None:
        """Get command and schema for a domain/command pair."""
        if domain == "config" and cmd_name == "show":
            schema = get_typer_command_schema(app, None)
            command = next((cmd for cmd in app.registered_commands if cmd.name is None), None)
            if command is None:
                return None
            return command, schema

        command_info = MCPServer._find_command_in_app(app, cmd_name)
        if command_info is None:
            command_info = MCPServer._find_command_in_groups(app, cmd_name)
        if command_info is None:
            return None

        command, schema_app, schema_cmd = command_info
        schema = get_typer_command_schema(schema_app, schema_cmd)
        return command, schema

    @staticmethod
    def define_tools() -> dict[str, dict[str, Any]]:
        """Build tool metadata from discovered CLI commands."""
        tools = {}
        for (domain, cmd_name), _cmd_func in discover_commands().items():
            app = get_app(domain)
            if app is None:
                continue

            result = MCPServer._get_command_and_schema(domain, cmd_name, app)
            if result is None:
                continue

            command, schema = result
            description = (
                command.callback.__doc__.split("\n")[0].strip()
                if (command and command.callback and command.callback.__doc__)
                else f"{domain} {cmd_name} operation"
            )
            tools[f"wksm_{domain}_{cmd_name}"] = {"description": description, "inputSchema": schema}

        tools["wksm_diff"] = {
            "description": "Compute a diff between two targets",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "config": {"type": "object"},
                    "target_a": {"type": "string"},
                    "target_b": {"type": "string"},
                },
                "required": ["config", "target_a", "target_b"],
            },
        }
        return tools

    def build_registry(self) -> dict[str, Callable[[WKSConfig, dict[str, Any]], dict[str, Any]]]:
        """Build a registry of tool handlers mapped by name."""
        registry: dict[str, Callable[[WKSConfig, dict[str, Any]], dict[str, Any]]] = {}
        for (domain, cmd_name), cmd_func in discover_commands().items():
            sig = inspect.signature(cmd_func)

            def make_handler(func: Callable, sig: inspect.Signature, _domain: str) -> Callable:
                def handler(_config: WKSConfig, args: dict[str, Any]) -> dict[str, Any]:
                    from wks.api.config.URI import URI

                    kwargs = {}
                    for param_name, param in sig.parameters.items():
                        if param_name == "self":
                            continue
                        # Handle URI conversion: MCP clients pass 'path', but API now expects 'uri'
                        val = args.get(param_name)
                        if val is None and param_name == "uri":
                            # Try 'path' as fallback for backward compatibility
                            val = args.get("path")
                        if val is not None:
                            if param_name == "query" and isinstance(val, dict):
                                val = json.dumps(val)
                            # Convert string path to URI for 'uri' parameters
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

            registry[f"wksm_{domain}_{cmd_name}"] = make_handler(cmd_func, sig, domain)

        def diff_handler(_config: WKSConfig, args: dict[str, Any]) -> dict[str, Any]:
            from wks.api.diff.cmd_diff import cmd_diff

            config = args.get("config")
            target_a = args.get("target_a")
            target_b = args.get("target_b")
            errors: list[str] = []
            if not isinstance(config, dict):
                errors.append(f"config must be an object (found: {type(config).__name__})")
            if not isinstance(target_a, str) or not target_a:
                errors.append("target_a must be a non-empty string")
            if not isinstance(target_b, str) or not target_b:
                errors.append("target_b must be a non-empty string")
            if errors:
                return {"success": False, "data": {}, "error": "; ".join(errors)}
            assert isinstance(config, dict)
            assert isinstance(target_a, str)
            assert isinstance(target_b, str)
            result = cmd_diff(config, target_a, target_b)
            list(result.progress_callback(result))
            return {"success": result.success, "data": result.output}

        registry["wksm_diff"] = diff_handler
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
