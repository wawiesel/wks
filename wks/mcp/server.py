import inspect
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, get_args, get_origin, get_type_hints

from wks.api.config.get_package_version import get_package_version
from wks.api.config.StageResult import StageResult
from wks.api.config.WKSConfig import WKSConfig

from .discover_commands import discover_commands

TOOLS_RESOURCE_URI = "mcp://wks/tools"

GENERIC_PARAM_DESCRIPTIONS: dict[str, str] = {
    "batch_size": "Optional embedding batch size to use for this run.",
    "blocking": "When true, keep the command attached instead of returning immediately.",
    "config": "Structured configuration payload for this operation.",
    "database": "Database name to inspect or modify.",
    "delete": "When true, remove the value instead of setting it.",
    "dest": "Destination path for the move operation.",
    "direction": "Direction filter for related links.",
    "engine": "Optional transform engine name to use.",
    "errors_only": "When true, only clear error entries.",
    "index": "Optional index name to use.",
    "k": "Maximum number of results to return.",
    "key": "Configuration key expressed as a dot path.",
    "limit": "Maximum number of records to return.",
    "list_name": "Configuration list name to inspect or modify.",
    "name": "Target name for the requested operation.",
    "output": "Optional output format or destination understood by the command.",
    "output_path": "Optional file path to write the result to.",
    "overrides": "Structured override values applied to the command.",
    "parser": "Optional parser name to force instead of automatic detection.",
    "path": "Filesystem path for the requested operation.",
    "priority": "Priority value to assign to the path.",
    "query": "Text query to search for.",
    "query_image": "Image path or URI to use as the search query.",
    "recursive": "When true, include nested content recursively.",
    "remote": "When true, include or target remote-backed records.",
    "restrict_dir": "Optional directory limit for the daemon or service.",
    "section": "Configuration section name to show.",
    "source": "Source path for the move operation.",
    "strategy": "Optional named search strategy to use.",
    "target": "Checksum, cached artifact, or filesystem path to read.",
    "target_a": "First target to compare.",
    "target_b": "Second target to compare.",
    "uri": "File or resource URI for the operation.",
    "value": "Value to set or add.",
}

TOOL_PARAM_DESCRIPTION_OVERRIDES: dict[str, dict[str, str]] = {
    "cat": {
        "engine": "Optional transform engine to run before returning content.",
        "output_path": "Optional file path to write the rendered content to.",
        "target": "Checksum, cached artifact, or filesystem path to read.",
    },
    "search": {
        "index": "Optional index name. Omit to use the configured default index or strategy.",
        "k": "Maximum number of ranked hits to return.",
        "query": "Text query to search for. Provide this for normal text retrieval.",
        "query_image": "Optional image path or URI for image-guided search.",
        "strategy": "Optional named search strategy. Mutually exclusive with `index`.",
    },
}

TOOL_SCHEMA_OVERRIDES: dict[str, dict[str, Any]] = {
    "cat": {
        "required": ["target"],
    },
    "search": {
        "anyOf": [{"required": ["query"]}, {"required": ["query_image"]}],
        "properties": {
            "k": {"minimum": 1},
            "query": {"minLength": 1},
            "query_image": {"minLength": 1},
        },
    },
}


def _tool_name(domain: str, cmd_name: str) -> str:
    """Build MCP tool name from domain/command pair."""
    if domain == "_root":
        return cmd_name
    if domain == cmd_name:
        return domain
    return f"{domain}_{cmd_name}"


def _unwrap_optional(annotation: Any) -> Any:
    """Return the non-None member of an Optional/union annotation when unambiguous."""
    args = get_args(annotation)
    if not args or type(None) not in args:
        return annotation
    non_none_args = [arg for arg in args if arg is not type(None)]
    if len(non_none_args) == 1:
        return non_none_args[0]
    return annotation


def _coerce_argument(annotation: Any, value: Any) -> Any:
    """Coerce JSON-decoded MCP arguments to the types expected by API commands."""
    annotation = _unwrap_optional(annotation)
    if isinstance(value, str) and isinstance(annotation, type) and issubclass(annotation, Path):
        return Path(value).expanduser()
    return value


def _schema_for_annotation(annotation: Any) -> dict[str, Any]:
    """Map a Python annotation to a JSON Schema fragment."""
    annotation = _unwrap_optional(annotation)
    if annotation == inspect.Parameter.empty:
        return {"type": "string"}

    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin is list:
        item_annotation = args[0] if args else inspect.Parameter.empty
        return {"type": "array", "items": _schema_for_annotation(item_annotation)}
    if origin is dict:
        return {"type": "object", "additionalProperties": True}
    if origin is not None and str(origin).endswith("Literal"):
        literal_values = list(args)
        if literal_values and all(isinstance(value, str) for value in literal_values):
            return {"type": "string", "enum": literal_values}
        if literal_values and all(isinstance(value, int) for value in literal_values):
            return {"type": "integer", "enum": literal_values}

    if annotation is int:
        return {"type": "integer"}
    if annotation is bool:
        return {"type": "boolean"}
    if annotation is float:
        return {"type": "number"}
    if annotation is dict:
        return {"type": "object", "additionalProperties": True}
    return {"type": "string"}


def _parameter_description(tool_name: str, param_name: str) -> str:
    """Return a human-readable description for a tool parameter."""
    tool_overrides = TOOL_PARAM_DESCRIPTION_OVERRIDES.get(tool_name, {})
    if param_name in tool_overrides:
        return tool_overrides[param_name]
    if param_name.startswith("prune_"):
        level = param_name.removeprefix("prune_").replace("_", "-")
        return f"When true, prune {level}-level log entries."
    if param_name in GENERIC_PARAM_DESCRIPTIONS:
        return GENERIC_PARAM_DESCRIPTIONS[param_name]
    return f"{param_name.replace('_', ' ').capitalize()} value for this operation."


def _merge_property_overrides(
    schema_properties: dict[str, Any],
    property_overrides: dict[str, dict[str, Any]],
) -> None:
    """Apply per-property JSON Schema overrides in place."""
    for property_name, override in property_overrides.items():
        if property_name not in schema_properties:
            continue
        schema_properties[property_name].update(override)


def _schema_from_func(tool_name: str, func: Callable) -> dict[str, Any]:
    """Generate a JSON schema from an API function's signature."""
    import typing

    sig = inspect.signature(func)
    try:
        hints = typing.get_type_hints(func)
    except Exception:
        hints = {}

    schema: dict[str, Any] = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
    for name, param in sig.parameters.items():
        if name in ("self", "ctx"):
            continue
        annotation = hints.get(name, param.annotation)
        property_schema = _schema_for_annotation(annotation)
        property_schema["description"] = _parameter_description(tool_name, name)
        if param.default not in (inspect.Parameter.empty, None, ""):
            property_schema["default"] = param.default
        schema["properties"][name] = property_schema
        if param.default == inspect.Parameter.empty:
            schema["required"].append(name)

    schema_override = TOOL_SCHEMA_OVERRIDES.get(tool_name)
    if schema_override:
        property_overrides = schema_override.get("properties", {})
        if property_overrides:
            _merge_property_overrides(schema["properties"], property_overrides)
        for key, value in schema_override.items():
            if key == "properties":
                continue
            schema[key] = value
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
            {
                "uri": TOOLS_RESOURCE_URI,
                "name": "wks-tools",
                "description": "WKS tools and search workflow guidance",
                "type": "tool-collection",
            },
        ]

    @staticmethod
    def define_tools() -> dict[str, dict[str, Any]]:
        """Build tool metadata from discovered API functions."""
        tools = {}
        for (domain, cmd_name), cmd_func in discover_commands().items():
            name = _tool_name(domain, cmd_name)
            tools[name] = {
                "description": _description_from_func(cmd_func, domain, cmd_name),
                "inputSchema": _schema_from_func(name, cmd_func),
            }
        return tools

    def build_registry(self) -> dict[str, Callable[[WKSConfig, dict[str, Any]], dict[str, Any]]]:
        """Build a registry of tool handlers mapped by name."""
        registry: dict[str, Callable[[WKSConfig, dict[str, Any]], dict[str, Any]]] = {}
        for (domain, cmd_name), cmd_func in discover_commands().items():
            sig = inspect.signature(cmd_func)
            try:
                hints = get_type_hints(cmd_func)
            except Exception:
                hints = {}

            def make_handler(func: Callable, sig: inspect.Signature, hints: dict[str, Any]) -> Callable:
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
                            annotation = hints.get(param_name, param.annotation)
                            if param_name == "query" and isinstance(val, dict):
                                val = json.dumps(val)
                            elif param_name == "uri" and isinstance(val, str):
                                val = URI.from_any(val)
                            else:
                                val = _coerce_argument(annotation, val)
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
            registry[name] = make_handler(cmd_func, sig, hints)

        return registry

    def _tools_resource_document(self) -> str:
        """Render the advertised tools resource as JSON text."""
        document: dict[str, Any] = {
            "server": "wks",
            "tools": [
                {"name": name, "description": info["description"], "inputSchema": info["inputSchema"]}
                for name, info in sorted(self.tools.items())
            ],
        }
        preferred_workflow: dict[str, str] = {}
        if "search" in self.tools:
            preferred_workflow["search"] = "search"
        if "cat" in self.tools:
            preferred_workflow["read"] = "cat"
        if preferred_workflow:
            document["preferred_workflow"] = preferred_workflow
        return json.dumps(document, indent=2)

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
                        "capabilities": {"tools": {}, "resources": {}},
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
        elif method == "resources/read":
            uri = params.get("uri")
            if uri != TOOLS_RESOURCE_URI:
                self.write_message(
                    {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {"code": -32601, "message": f"Resource not found: {uri}"},
                    }
                )
                return
            self.write_message(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "contents": [
                            {
                                "uri": TOOLS_RESOURCE_URI,
                                "mimeType": "application/json",
                                "text": self._tools_resource_document(),
                            }
                        ]
                    },
                }
            )
        elif method == "resources/templates/list":
            self.write_message({"jsonrpc": "2.0", "id": request_id, "result": {"resourceTemplates": []}})
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
