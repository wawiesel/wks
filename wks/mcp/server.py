"""MCP Server for WKS - Auto-discovers cmd_* functions and exposes as MCP tools."""

import importlib
import inspect
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from wks.api.StageResult import StageResult
from wks.cli.get_typer_command_schema import get_typer_command_schema
from wks.api.config.WKSConfig import WKSConfig


def _extract_api_function_from_command(cmd_callback: Callable, cli_module: Any) -> Callable | None:
    """Extract underlying API function from a Typer command callback.

    Handles two patterns:
    1. Direct: command = handle_stage_result(cmd_*) -> has __wrapped__
    2. Wrapper: command = wrapper_function that calls handle_stage_result(cmd_*)

    Args:
        cmd_callback: The Typer command callback function
        cli_module: The CLI module (to access imported API functions)

    Returns:
        The underlying API function, or None if not found
    """
    # Pattern 1: Direct command with __wrapped__
    if hasattr(cmd_callback, '__wrapped__'):
        return cmd_callback.__wrapped__

    # Pattern 2: Wrapper command - extract from module globals
    # CLI modules import API functions like: from wks.api.monitor.cmd_check import cmd_check
    # The wrapper calls handle_stage_result(cmd_check), so cmd_check is in module globals
    if hasattr(cli_module, '__dict__'):
        # Try to find cmd_* function in module that matches command name
        # We need to infer the command name from the callback name
        callback_name = cmd_callback.__name__
        # Wrapper commands are like: check_command -> cmd_check
        if callback_name.endswith('_command'):
            cmd_name = callback_name[:-8]  # Remove '_command' suffix
            func_name = f"cmd_{cmd_name}"
            if hasattr(cli_module, func_name):
                func = getattr(cli_module, func_name)
                if callable(func):
                    return func

    return None


def _discover() -> dict[tuple[str, str], Callable]:
    """Auto-discover all cmd_* functions by scanning CLI Typer apps.

    This makes CLI the single source of truth - MCP discovers commands
    through CLI infrastructure rather than scanning API directories directly.
    """
    commands: dict[tuple[str, str], Callable] = {}
    cli_path = Path(__file__).parent.parent / "cli"

    # Scan CLI modules for Typer apps
    for cli_file in cli_path.glob("*.py"):
        if cli_file.name.startswith("_") or cli_file.name == "__init__.py":
            continue

        domain = cli_file.stem
        if domain == "display":  # Skip display.py
            continue

        try:
            # Import CLI module
            cli_module = importlib.import_module(f"wks.cli.{domain}")

            # Get Typer app (try common patterns)
            app = None
            patterns = [f"{domain}_app", "db_app" if domain == "database" else None, f"{domain}app", "app"]
            for pattern in patterns:
                if pattern is None:
                    continue
                app = getattr(cli_module, pattern, None)
                if app is not None:
                    break

            if app is None:
                continue

            # Extract commands from app
            for cmd in app.registered_commands:
                if cmd.name is None:
                    continue

                # Extract underlying API function
                api_func = _extract_api_function_from_command(cmd.callback, cli_module)
                if api_func:
                    commands[(domain, cmd.name)] = api_func

            # Handle sub-apps (filter_app, priority_app, etc.)
            if hasattr(app, "registered_groups"):
                for group in app.registered_groups:
                    if not hasattr(group, "typer_instance"):
                        continue
                    sub_app = group.typer_instance
                    prefix = f"{group.name}_"

                    for cmd in sub_app.registered_commands:
                        api_func = _extract_api_function_from_command(cmd.callback, cli_module)
                        if api_func:
                            full_cmd_name = f"{prefix}{cmd.name}"
                            commands[(domain, full_cmd_name)] = api_func

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
            module = importlib.import_module(f"wks.cli.{domain}")
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
