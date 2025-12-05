"""
MCP Server for WKS - Model Context Protocol integration.

Exposes WKS functionality as MCP tools via stdio transport.
Uses existing controllers for zero code duplication per SPEC.md.

MCP is the source of truth for all errors, warnings, and messages.
All MCP tools return structured MCPResult objects.
"""

import json
import sys
from collections.abc import Callable
from typing import Any

from .api.base import StageResult, get_typer_command_schema
from .api.monitor.cmd_check import cmd_check as monitor_check
from .api.monitor.cmd_filter_show import cmd_filter_show as cmd_show
from .api.monitor.cmd_filter_add import cmd_filter_add as cmd_add
from .api.monitor.cmd_filter_remove import cmd_filter_remove as cmd_remove
from .api.monitor.cmd_status import cmd_status as monitor_status
from .api.monitor.cmd_sync import cmd_sync
from .api.monitor.cmd_priority_show import cmd_priority_show
from .api.monitor.cmd_priority_add import cmd_priority_add
from .api.monitor.cmd_priority_remove import cmd_priority_remove
from .config import WKSConfig
from .mcp.result import MCPResult
from .api.monitor.cmd_check import cmd_check
from .api.monitor.cmd_filter_add import cmd_filter_add
from .api.monitor.cmd_filter_remove import cmd_filter_remove
from .api.monitor.cmd_filter_show import cmd_filter_show
from .api.monitor.cmd_priority_add import cmd_priority_add
from .api.monitor.cmd_priority_remove import cmd_priority_remove
from .api.monitor.cmd_priority_show import cmd_priority_show
from .api.monitor.cmd_status import cmd_status
from .service_controller import ServiceController
from .vault import VaultController
from .vault.status_controller import VaultStatusController


def _extract_data_from_stage_result(result: Any) -> dict[str, Any]:
    """Extract data from StageResult or return as-is."""
    if isinstance(result, StageResult):
        return result.output
    return result if isinstance(result, dict) else {}


class MCPServer:
    """MCP server exposing WKS tools via stdio."""

    @staticmethod
    def _define_transform_tools() -> dict[str, dict[str, Any]]:
        """Define transform-related tools.

        Returns:
            Dictionary of transform tool definitions
        """
        return {
            "wksm_transform": {
                "description": "Transform a file using a specific engine",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Path to file to transform"},
                        "engine": {
                            "type": "string",
                            "description": "Transform engine name (e.g., 'docling')",
                        },
                        "options": {"type": "object", "description": "Engine-specific options"},
                    },
                    "required": ["file_path", "engine"],
                },
            },
            "wksm_cat": {
                "description": "Retrieve content for a target (checksum or file path)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "target": {
                            "type": "string",
                            "description": "Checksum (64 hex chars) or file path",
                        }
                    },
                    "required": ["target"],
                },
            },
            "wksm_diff": {
                "description": "Calculate diff between two targets",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "engine": {
                            "type": "string",
                            "description": "Diff engine name (e.g., 'bsdiff3', 'myers')",
                        },
                        "target_a": {
                            "type": "string",
                            "description": "First target (file path or checksum)",
                        },
                        "target_b": {
                            "type": "string",
                            "description": "Second target (file path or checksum)",
                        },
                    },
                    "required": ["engine", "target_a", "target_b"],
                },
            },
        }

    @staticmethod
    def _define_service_tools() -> dict[str, dict[str, Any]]:
        """Define service-related tools.

        Returns:
            Dictionary of service tool definitions
        """
        return {
            "wksm_service": {
                "description": "Get daemon/service status summary",
                "inputSchema": {"type": "object", "properties": {}, "required": []},
            },
        }

    @staticmethod
    def _define_vault_tools() -> dict[str, dict[str, Any]]:
        """Define vault-related tools.

        Returns:
            Dictionary of vault tool definitions
        """
        return {
            "wksm_vault_validate": {
                "description": "Validate all vault links",
                "inputSchema": {"type": "object", "properties": {}, "required": []},
            },
            "wksm_vault_fix_symlinks": {
                "description": "Rebuild _links/<machine>/ from vault DB",
                "inputSchema": {"type": "object", "properties": {}, "required": []},
            },
        }

    @staticmethod
    def _define_db_tools() -> dict[str, dict[str, Any]]:
        """Define database query tools.

        Returns:
            Dictionary of database tool definitions
        """
        return {
            "wksm_db_monitor": {
                "description": "Query filesystem database",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "object", "description": "MongoDB query object"},
                        "limit": {"type": "integer", "description": "Max results"},
                    },
                    "required": [],
                },
            },
            "wksm_db_vault": {
                "description": "Query vault database",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "object", "description": "MongoDB query object"},
                        "limit": {"type": "integer", "description": "Max results"},
                    },
                    "required": [],
                },
            },
            "wksm_db_transform": {
                "description": "Query transform database",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "object", "description": "MongoDB query object"},
                        "limit": {"type": "integer", "description": "Max results"},
                    },
                    "required": [],
                },
            },
        }

    @staticmethod
    def _define_monitor_basic_tools() -> dict[str, dict[str, Any]]:
        """Define basic monitor tools (status, check) using Typer introspection.

        Returns:
            Dictionary of basic monitor tool definitions
        """
        from .api.monitor import monitor_app

        tools = {}
        for cmd_name in ["status", "check", "sync"]:
            schema = get_typer_command_schema(monitor_app, cmd_name)
            mcp_tool_name = f"wksm_monitor_{cmd_name}"
            # Get command description from docstring or use default
            command = None
            for cmd in monitor_app.registered_commands:
                if cmd.name == cmd_name:
                    command = cmd
                    break
            description = "Monitor operation"
            if command and command.callback:
                doc = command.callback.__doc__ or ""
                if doc:
                    description = doc.split("\n")[0].strip()
            tools[mcp_tool_name] = {
                "description": description,
                "inputSchema": schema,
            }
        return tools

    @staticmethod
    def _define_monitor_list_tools() -> dict[str, dict[str, Any]]:
        """Define monitor filter tools (show/add/remove).

        Returns:
            Dictionary of monitor list tool definitions
        """
        list_name_enum = [
            "include_paths",
            "exclude_paths",
            "include_dirnames",
            "exclude_dirnames",
            "include_globs",
            "exclude_globs",
        ]
        return {
            "wksm_monitor_filter_show": {
                "description": (
                    "Show contents of a monitor configuration list or list available monitor lists"
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "list_name": {
                            "type": "string",
                            "description": "Name of the list to retrieve (optional)",
                            "enum": list_name_enum,
                        }
                    },
                    "required": [],
                },
            },
            "wksm_monitor_filter_add": {
                "description": "Add a value to a monitor configuration list",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "list_name": {
                            "type": "string",
                            "description": "Name of the list to modify",
                            "enum": list_name_enum,
                        },
                        "value": {
                            "type": "string",
                            "description": (
                                "Value to add (path for include/exclude_paths, "
                                "dirname for include/exclude_dirnames, "
                                "pattern for include/exclude_globs)"
                            ),
                        },
                    },
                    "required": ["list_name", "value"],
                },
            },
            "wksm_monitor_filter_remove": {
                "description": "Remove a value from a monitor configuration list",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "list_name": {
                            "type": "string",
                            "description": "Name of the list to modify",
                            "enum": list_name_enum,
                        },
                        "value": {"type": "string", "description": "Value to remove"},
                    },
                    "required": ["list_name", "value"],
                },
            },
        }

    @staticmethod
    def _define_monitor_managed_tools() -> dict[str, dict[str, Any]]:
        """Define monitor priority tools."""
        return {
            "wksm_monitor_priority_show": {
                "description": "Get all managed directories with their priorities",
                "inputSchema": {"type": "object", "properties": {}, "required": []},
            },
            "wksm_monitor_priority_add": {
                "description": "Set or update priority for a managed directory (creates if missing)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Directory path"},
                        "priority": {"type": "number", "description": "Priority score (float)"},
                    },
                    "required": ["path", "priority"],
                },
            },
            "wksm_monitor_priority_remove": {
                "description": "Remove a managed directory",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Directory path to remove"},
                    },
                    "required": ["path"],
                },
            },
        }

    @staticmethod
    def _define_monitor_tools() -> dict[str, dict[str, Any]]:
        """Define all monitor-related tools.

        Returns:
            Dictionary of monitor tool definitions
        """
        tools = {}
        tools.update(MCPServer._define_monitor_basic_tools())
        tools.update(MCPServer._define_monitor_list_tools())
        tools.update(MCPServer._define_monitor_managed_tools())
        return tools

    @staticmethod
    def _define_vault_advanced_tools() -> dict[str, dict[str, Any]]:
        """Define advanced vault tools.

        Returns:
            Dictionary of advanced vault tool definitions
        """
        return {
            "wksm_vault_status": {
                "description": "Get vault link status summary including link counts, issues, and errors",
                "inputSchema": {"type": "object", "properties": {}, "required": []},
            },
            "wksm_vault_sync": {
                "description": "Sync vault links to MongoDB with optional batch size",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "batch_size": {
                            "type": "integer",
                            "description": "Number of records to process per batch (default 1000)",
                        }
                    },
                    "required": [],
                },
            },
            "wksm_vault_links": {
                "description": "Get all links to and from a specific vault file",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to the vault file (e.g., ~/_vault/Projects/XYZ.md)",
                        },
                        "direction": {
                            "type": "string",
                            "description": (
                                "Link direction filter: 'both' (default), "
                                "'to' (incoming only), or 'from' (outgoing only)"
                            ),
                            "enum": ["both", "to", "from"],
                        },
                    },
                    "required": ["file_path"],
                },
            },
        }

    @staticmethod
    def _define_tools() -> dict[str, dict[str, Any]]:
        """Define all MCP tools with their schemas.

        Returns:
            Dictionary mapping tool names to tool definitions
        """
        tools = {}
        tools.update(
            {
                "wksm_config": {
                    "description": "Get effective configuration",
                    "inputSchema": {"type": "object", "properties": {}, "required": []},
                }
            }
        )
        tools.update(MCPServer._define_transform_tools())
        tools.update(MCPServer._define_service_tools())
        tools.update(MCPServer._define_vault_tools())
        tools.update(MCPServer._define_db_tools())
        tools.update(MCPServer._define_monitor_tools())
        tools.update(MCPServer._define_vault_advanced_tools())
        return tools

    @staticmethod
    def _define_resources() -> list[dict[str, Any]]:
        """Define MCP resources.

        Returns:
            List of resource definitions
        """
        return [
            {
                "uri": "mcp://wks/tools",
                "name": "wks-tools",
                "description": "WKS monitor and vault tooling available via tools/call",
                "type": "tool-collection",
            }
        ]

    def __init__(
        self,
        *,
        input_stream: Any | None = None,
        output_stream: Any | None = None,
    ):
        """Initialize MCP server."""
        import sys

        self._input = input_stream or sys.stdin
        self._output = output_stream or sys.stdout
        self._lsp_mode = False
        self.tools = MCPServer._define_tools()
        self.resources = MCPServer._define_resources()

    def _read_content_length_message(self, header_line: str) -> dict[str, Any] | None:
        """Read message using Content-Length framing (LSP mode).

        Args:
            header_line: The Content-Length header line

        Returns:
            Parsed JSON message or None on error

        Raises:
            ValueError: If Content-Length header is invalid
        """
        self._lsp_mode = True
        try:
            length = int(header_line.split(":", 1)[1].strip())
        except Exception as e:
            raise ValueError(f"Invalid Content-Length header: {header_line!r}") from e

        # Consume the blank line after headers
        while True:
            sep = self._input.readline()
            if sep == "":
                break
            if sep in ("\r\n", "\n", "\r"):
                break
            if not sep.strip():
                break

        payload = self._input.read(length)
        if payload is None:
            return None
        return json.loads(payload)

    def _read_message(self) -> dict[str, Any] | None:
        """Read JSON-RPC message supporting newline or Content-Length framing."""
        try:
            while True:
                line = self._input.readline()
                if not line:
                    return None
                stripped = line.strip()
                if not stripped:
                    continue
                lowered = stripped.lower()
                if lowered.startswith("content-length"):
                    return self._read_content_length_message(stripped)
                else:
                    return json.loads(line)
        except Exception as e:
            sys.stderr.write(f"Parse error: {e}\n")
            return None

    def _write_message(self, message: dict[str, Any]) -> None:
        """Write JSON-RPC message using negotiated framing."""
        payload = json.dumps(message)
        if self._lsp_mode:
            encoded = payload.encode("utf-8")
            self._output.write(f"Content-Length: {len(encoded)}\r\n\r\n")
            self._output.write(payload)
        else:
            self._output.write(payload)
        self._output.write("\n")
        self._output.flush()

    def _write_response(self, request_id: Any, result: Any) -> None:
        """Write JSON-RPC response."""
        self._write_message({"jsonrpc": "2.0", "id": request_id, "result": result})

    def _write_error(self, request_id: Any, code: int, message: str, data: Any = None) -> None:
        """Write JSON-RPC error response."""
        error = {"code": code, "message": message}
        if data is not None:
            error["data"] = data
        self._write_message({"jsonrpc": "2.0", "id": request_id, "error": error})

    def _handle_initialize(self, request_id: Any, params: dict[str, Any]) -> None:  # noqa: ARG002
        """Handle initialize request."""
        self._write_response(
            request_id,
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}, "resources": {}},
                "serverInfo": {"name": "wks-mcp-server", "version": "1.0.0"},
            },
        )

    def _handle_list_tools(self, request_id: Any) -> None:
        """Handle tools/list request."""
        tools_list = [
            {"name": name, "description": info["description"], "inputSchema": info["inputSchema"]}
            for name, info in self.tools.items()
        ]
        self._write_response(request_id, {"tools": tools_list})

    def _handle_list_resources(self, request_id: Any, params: dict[str, Any]) -> None:
        """Handle resources/list request with a single static page."""
        if request_id is None:
            return

        # Basic pagination contract—single page only.
        result: dict[str, Any] = {"resources": self.resources}
        if params.get("cursor") is not None:
            result["nextCursor"] = None
        self._write_response(request_id, result)

    def _build_tool_registry(self) -> dict[str, Callable[[WKSConfig, dict[str, Any]], dict[str, Any]]]:
        """Build registry of tool handlers with parameter validation."""

        def _require_params(
            *param_names: str,
        ) -> Callable[
            [Callable[[WKSConfig, dict[str, Any]], dict[str, Any]]],
            Callable[[WKSConfig, dict[str, Any]], dict[str, Any]],
        ]:
            """Decorator to validate required parameters."""

            def decorator(
                handler: Callable[[WKSConfig, dict[str, Any]], dict[str, Any]],
            ) -> Callable[[WKSConfig, dict[str, Any]], dict[str, Any]]:
                def wrapper(config: WKSConfig, arguments: dict[str, Any]) -> dict[str, Any]:
                    missing = [p for p in param_names if arguments.get(p) is None]
                    if missing:
                        raise ValueError(f"Missing required parameters: {', '.join(missing)}")
                    return handler(config, arguments)

                return wrapper

            return decorator

        return {
            "wksm_config": lambda config, args: self._tool_config(config),  # noqa: ARG005
            "wksm_transform": _require_params("file_path", "engine")(
                lambda config, args: self._tool_transform(
                    config, args["file_path"], args["engine"], args.get("options", {})
                )
            ),
            "wksm_cat": _require_params("target")(lambda config, args: self._tool_cat(config, args["target"])),
            "wksm_diff": _require_params("engine", "target_a", "target_b")(
                lambda config, args: self._tool_diff(config, args["engine"], args["target_a"], args["target_b"])
            ),
            "wksm_service": lambda config, args: self._tool_service(config),  # noqa: ARG005
            "wksm_vault_validate": lambda config, args: self._tool_vault_validate(config),  # noqa: ARG005
            "wksm_vault_fix_symlinks": lambda config, args: self._tool_vault_fix_symlinks(config),  # noqa: ARG005
            "wksm_db_monitor": lambda config, args: self._tool_db_query(
                config, "monitor", args.get("query", {}), args.get("limit", 50)
            ),
            "wksm_db_vault": lambda config, args: self._tool_db_query(
                config, "vault", args.get("query", {}), args.get("limit", 50)
            ),
            "wksm_db_transform": lambda config, args: self._tool_db_query(
                config, "transform", args.get("query", {}), args.get("limit", 50)
            ),
            "wksm_monitor_status": lambda config, args: MCPResult(  # noqa: ARG005
                success=True, data=_extract_data_from_stage_result(monitor_status())
            ).to_dict(),
            "wksm_monitor_check": _require_params("path")(
                lambda config, args: MCPResult(  # noqa: ARG005
                    success=True, data=_extract_data_from_stage_result(monitor_check(path=args["path"]))
                ).to_dict()
            ),
            "wksm_monitor_filter_show": lambda config, args: MCPResult(  # noqa: ARG005
                success=True,
                data=_extract_data_from_stage_result(cmd_filter_show(list_name=args.get("list_name"))),
            ).to_dict(),
            "wksm_monitor_filter_add": _require_params("list_name", "value")(
                lambda config, args: MCPResult(  # noqa: ARG005
                    success=True, data=_extract_data_from_stage_result(cmd_add(list_name=args["list_name"], value=args["value"]))
                ).to_dict()
            ),
            "wksm_monitor_filter_remove": _require_params("list_name", "value")(
                lambda config, args: MCPResult(  # noqa: ARG005
                    success=True, data=_extract_data_from_stage_result(cmd_remove(list_name=args["list_name"], value=args["value"]))
                ).to_dict()
            ),
            "wksm_monitor_sync": _require_params("path")(
                lambda config, args: MCPResult(  # noqa: ARG005
                    success=True, data=_extract_data_from_stage_result(cmd_sync(path=args["path"], recursive=args.get("recursive", False)))
                ).to_dict()
            ),
            "wksm_monitor_priority_show": lambda config, args: MCPResult(  # noqa: ARG005
                success=True, data=_extract_data_from_stage_result(cmd_priority_show())
            ).to_dict(),
            "wksm_monitor_priority_add": _require_params("path", "priority")(
                lambda config, args: MCPResult(  # noqa: ARG005
                    success=True,
                    data=_extract_data_from_stage_result(
                        cmd_priority_add(path=args["path"], priority=args["priority"])
                    ),
                ).to_dict()
            ),
            "wksm_monitor_priority_remove": _require_params("path")(
                lambda config, args: MCPResult(  # noqa: ARG005
                    success=True,
                    data=_extract_data_from_stage_result(cmd_priority_remove(path=args["path"])),
                ).to_dict()
            ),
            "wksm_vault_status": lambda config, args: self._tool_vault_status(config),  # noqa: ARG005
            "wksm_vault_sync": lambda config, args: self._tool_vault_sync(config, args.get("batch_size", 1000)),
            "wksm_vault_links": _require_params("file_path")(
                lambda config, args: self._tool_vault_links(config, args["file_path"], args.get("direction", "both"))
            ),
        }

    def _handle_call_tool(self, request_id: Any, params: dict[str, Any]) -> None:
        """Handle tools/call request using registry pattern."""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if tool_name not in self.tools:
            self._write_error(request_id, -32601, f"Tool not found: {tool_name}")
            return

        try:
            config = WKSConfig.load()
            registry = self._build_tool_registry()

            if tool_name not in registry:
                self._write_error(request_id, -32601, f"Tool not implemented: {tool_name}")
                return

            handler = registry[tool_name]
            result = handler(config, arguments)

            self._write_response(request_id, {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]})

        except ValueError as e:
            self._write_error(request_id, -32602, str(e))
        except Exception as e:
            self._write_error(request_id, -32000, f"Tool execution failed: {e}", {"traceback": str(e)})

    def _tool_service(self, config: WKSConfig) -> dict[str, Any]:  # noqa: ARG002
        """Execute wksm_service tool."""
        status = ServiceController.get_status()
        result = MCPResult.success_result(
            status.to_dict(),
            "Service status retrieved successfully",
        )
        return result.to_dict()

    def _tool_monitor_list(self, config: WKSConfig, list_name: str) -> dict[str, Any]:
        """Execute wks_monitor_list tool."""
        result = cmd_filter_show(list_name)
        return result.output

    def _tool_monitor_add(self, config: WKSConfig, list_name: str, value: str) -> dict[str, Any]:
        """Execute wks_monitor_add tool."""
        result = cmd_filter_add(list_name, value)
        output = result.output
        if output.get("success"):
            config.save()
            output["note"] = "Restart the monitor service for changes to take effect"
        return output

    def _tool_monitor_remove(self, config: WKSConfig, list_name: str, value: str) -> dict[str, Any]:
        """Execute wks_monitor_remove tool."""
        result = cmd_filter_remove(list_name, value)
        output = result.output
        if output.get("success"):
            config.save()
            output["note"] = "Restart the monitor service for changes to take effect"
        return output

    def _tool_monitor_managed_list(self, config: WKSConfig) -> dict[str, Any]:
        """Execute wks_monitor_managed_list tool."""
        result = cmd_priority_show()
        return result.output

    def _tool_monitor_managed_remove(self, config: WKSConfig, path: str) -> dict[str, Any]:
        """Legacy helper (unused)."""
        result = cmd_priority_remove(path)
        return result.output

    def _tool_monitor_managed_set_priority(self, config: WKSConfig, path: str, priority: float) -> dict[str, Any]:
        """Legacy helper (unused)."""
        result = cmd_priority_add(path, priority)
        return result.output

    def _tool_vault_status(self, config: WKSConfig) -> dict[str, Any]:
        """Execute wks_vault_status tool."""
        # VaultStatusController expects dict, convert WKSConfig
        config_dict = config.to_dict()
        controller = VaultStatusController(config_dict)
        summary = controller.summarize()
        return summary.to_dict()

    def _tool_vault_sync(self, config: WKSConfig, batch_size: int) -> dict[str, Any]:
        """Execute wks_vault_sync tool."""
        # VaultController.sync_vault expects dict, convert WKSConfig
        config_dict = config.to_dict()
        return VaultController.sync_vault(config_dict, batch_size)

    def _tool_vault_links(self, config: WKSConfig, file_path: str, direction: str = "both") -> dict[str, Any]:
        """Execute wks_vault_links tool."""
        from .db_helpers import connect_to_mongo, get_vault_db_config
        from .uri_utils import convert_to_uri
        from .utils import expand_path

        # Get vault configuration
        vault_path_str = config.vault.base_dir
        if not vault_path_str:
            return {"error": "vault.base_dir not configured"}

        vault_path = expand_path(vault_path_str)

        # Expand and normalize the file path
        file_path_expanded = expand_path(file_path)

        # Check if file exists
        if not file_path_expanded.exists():
            return {"error": f"File does not exist: {file_path_expanded}"}

        # Check if file is monitored
        try:
            result = cmd_check(str(file_path_expanded))
            output = result.output
            is_monitored = output.get("is_monitored", False)
            priority = output.get("priority", 0) if is_monitored else None
        except Exception:
            is_monitored = False
            priority = None

        # Convert to URI using central conversion function
        target_uri = convert_to_uri(file_path_expanded, vault_path)

        # Also get version without .md extension for fallback matching
        target_uri_no_ext = target_uri[:-3] if target_uri.endswith(".md") else target_uri

        # Connect to database
        from pymongo import MongoClient

        uri, db_name, coll_name = get_vault_db_config(config.to_dict())
        client: MongoClient = connect_to_mongo(uri)
        coll = client[db_name][coll_name]

        result = {
            "file": target_uri,
            "is_monitored": is_monitored,
            "priority": priority if is_monitored else None,
        }

        # Query for links FROM this file (URI-only, no legacy path fallbacks)
        is_external = not target_uri.startswith("vault://")
        if direction in ("both", "from") and not is_external:
            from_query = {
                "doc_type": "link",
                "$or": [{"from_uri": target_uri}, {"from_uri": target_uri_no_ext}],
            }
            links_from = list(coll.find(from_query, {"_id": 0}))
            result["links_from"] = links_from

        # Query for links TO this file (URI-only, no legacy path fallbacks)
        if direction in ("both", "to"):
            to_query = {
                "doc_type": "link",
                "$or": [{"to_uri": target_uri}, {"to_uri": target_uri_no_ext}],
            }
            links_to = list(coll.find(to_query, {"_id": 0}))
            result["links_to"] = links_to

        client.close()
        return result

    def _handle_request(self, message: dict[str, Any]) -> None:
        """Handle a single request message.

        Args:
            message: Request message dictionary
        """
        request_id = message.get("id")
        method = message.get("method")
        params = message.get("params", {})

        # Handle different methods
        if method == "initialize":
            self._handle_initialize(request_id, params)
        elif method == "initialized" or method == "notifications/initialized":
            # Notification, no response needed
            pass
        elif method == "tools/list":
            self._handle_list_tools(request_id)
        elif method == "resources/list":
            self._handle_list_resources(request_id, params)
        elif method == "tools/call":
            self._handle_call_tool(request_id, params)
        elif method == "ping":
            self._write_response(request_id, {})
        else:
            # Only send error if this is a request (has ID), not a notification
            if request_id is not None:
                self._write_error(request_id, -32601, f"Method not found: {method}")

    def run(self) -> None:
        """Run MCP server main loop."""
        while True:
            message = self._read_message()
            if message is None:
                break
            self._handle_request(message)

    def _tool_config(self, config: WKSConfig | dict[str, Any]) -> dict[str, Any]:
        """Execute wksm_config tool.

        Accepts either a WKSConfig instance (normal runtime) or a raw dict
        (used in some tests that patch WKSConfig.load()).
        """
        data = config.to_dict() if hasattr(config, "to_dict") else dict(config)

        result = MCPResult(success=True, data=data)
        result.add_success("Configuration loaded successfully")
        return result.to_dict()

    def _tool_transform(
        self,
        config: WKSConfig,  # noqa: ARG002
        file_path: str,
        engine: str,
        options: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute wksm_transform tool."""
        from pathlib import Path

        from .config import WKSConfig
        from .db_helpers import connect_to_mongo
        from .transform import TransformController
        from .utils import expand_path

        result = MCPResult(success=False, data={})

        try:
            # Validate file exists
            path = expand_path(file_path)
            if not path.exists():
                return result.error_result(f"File not found: {path}", data={}).to_dict()

            # Use global WKSConfig (tests patch WKSConfig.load accordingly)
            wks_cfg = WKSConfig.load()
            cache_location = Path(wks_cfg.transform.cache.location).expanduser()
            max_size_bytes = wks_cfg.transform.cache.max_size_bytes

            from pymongo import MongoClient

            uri = wks_cfg.db.get_uri()
            db_name = wks_cfg.transform.database.split(".")[0]

            client: MongoClient = connect_to_mongo(uri)
            db = client[db_name]

            controller = TransformController(db, cache_location, max_size_bytes)

            # Transform
            result.add_status(f"Transforming {path.name} using {engine}...")
            cache_key = controller.transform(path, engine, options)

            return result.success_result({"checksum": cache_key}, "Transform completed successfully").to_dict()

        except ValueError as e:
            return result.error_result(f"Invalid input: {e!s}", data={}).to_dict()
        except RuntimeError as e:
            return result.error_result(f"Transform failed: {e!s}", data={}).to_dict()
        except Exception as e:
            return result.error_result(f"Unexpected error: {e!s}", details=str(e), data={}).to_dict()

    def _tool_cat(self, config: WKSConfig, target: str) -> dict[str, Any]:  # noqa: ARG002
        """Execute wksm_cat tool."""
        from pathlib import Path

        from .config import WKSConfig
        from .db_helpers import connect_to_mongo
        from .transform import TransformController

        result = MCPResult(success=False, data={})

        try:
            # Load config dataclass for proper cache location resolution
            wks_cfg = WKSConfig.load()
            cache_location = Path(wks_cfg.transform.cache.location).expanduser()
            max_size_bytes = wks_cfg.transform.cache.max_size_bytes

            from .api.db.helpers import get_database

            db_name = wks_cfg.transform.database.split(".")[0]
            db = get_database(db_name)

            controller = TransformController(db, cache_location, max_size_bytes)

            # Get content
            content = controller.get_content(target)

            return result.success_result({"content": content}, "Content retrieved successfully").to_dict()

        except FileNotFoundError as e:
            return result.error_result(f"File or cache entry not found: {target}", details=str(e), data={}).to_dict()
        except Exception as e:
            return result.error_result(f"Failed to retrieve content: {e!s}", details=str(e), data={}).to_dict()

    def _tool_diff(
        self,
        config: WKSConfig | dict[str, Any],
        engine: str,
        target_a: str,
        target_b: str,
    ) -> dict[str, Any]:
        """Execute wksm_diff tool."""
        from pathlib import Path

        from .db_helpers import connect_to_mongo
        from .diff import DiffController
        from .diff.config import DiffConfig, DiffConfigError
        from .transform import TransformController

        result = MCPResult(success=False, data={})

        try:
            # Setup transform controller for checksum resolution
            if isinstance(config, WKSConfig):
                transform_cfg = {
                    "cache_location": config.transform.cache.location,
                    "cache_max_size_bytes": config.transform.cache.max_size_bytes,
                    "database": config.transform.database,
                }
                raw_config: dict[str, Any] = config.to_dict()
            else:
                transform_cfg = config.get("transform", {})
                raw_config = config

            if isinstance(transform_cfg, dict):
                cache_location_str = transform_cfg.get("cache_location", "~/.wks/cache")
                max_size_bytes_val = transform_cfg.get("cache_max_size_bytes", 1024 * 1024 * 1024)
                db_name_str = transform_cfg.get("database", "wks.transform")
            else:
                cache_location_str = getattr(transform_cfg, "cache_location", "~/.wks/cache")
                max_size_bytes_val = getattr(transform_cfg, "cache_max_size_bytes", 1024 * 1024 * 1024)
                db_name_str = getattr(transform_cfg, "database", "wks.transform")

            cache_location = Path(str(cache_location_str)).expanduser()
            max_size_bytes: int = (
                int(max_size_bytes_val) if isinstance(max_size_bytes_val, (int, str)) else 1024 * 1024 * 1024
            )

            from pymongo import MongoClient

            db_name = str(db_name_str).split(".")[0]

            client: MongoClient = connect_to_mongo(uri)
            db = client[db_name]

            transform_controller = TransformController(db, cache_location, max_size_bytes)

            # Load diff configuration and construct controller when available.
            try:
                diff_config = DiffConfig.from_config_dict(raw_config)
            except DiffConfigError:
                diff_config = None

            diff_controller = DiffController(diff_config, transform_controller)

            # Diff
            diff_result = diff_controller.diff(target_a, target_b, engine)

            client.close()

            return result.success_result({"diff": diff_result}, f"Diff computed successfully using {engine}").to_dict()

        except ValueError as e:
            return result.error_result(f"Invalid input: {e!s}", details=str(e), data={}).to_dict()
        except RuntimeError as e:
            return result.error_result(f"Diff failed: {e!s}", details=str(e), data={}).to_dict()
        except Exception as e:
            return result.error_result(f"Unexpected error: {e!s}", details=str(e), data={}).to_dict()

    def _tool_vault_validate(self, config: WKSConfig | dict[str, Any]) -> dict[str, Any]:
        """Execute wks_vault_validate tool."""
        from .vault import VaultController, load_vault

        # load_vault expects a plain dict
        config_dict = config.to_dict() if hasattr(config, "to_dict") else dict(config)
        vault = load_vault(config_dict)
        controller = VaultController(vault)
        return controller.validate_vault()

    def _tool_vault_fix_symlinks(self, config: WKSConfig | dict[str, Any]) -> dict[str, Any]:
        """Execute wks_vault_fix_symlinks tool."""
        from .vault import VaultController, load_vault

        # load_vault expects a plain dict
        config_dict = config.to_dict() if hasattr(config, "to_dict") else dict(config)
        vault = load_vault(config_dict)
        controller = VaultController(vault)
        result = controller.fix_symlinks()

        # Convert dataclass to dict
        return {
            "notes_scanned": result.notes_scanned,
            "links_found": result.links_found,
            "created": result.created,
            "failed": result.failed,
        }

    def _tool_db_query(
        self,
        config: WKSConfig | dict[str, Any],
        db_type: str,
        query: dict[str, Any],
        limit: int,
    ) -> dict[str, Any]:
        """Execute wks_db_* tools."""
        from .api.db.query import query as db_query

        if isinstance(config, WKSConfig):
            if db_type == "monitor":
                database_key = config.monitor.sync.database
            elif db_type == "vault":
                database_key = config.vault.database
            elif db_type == "transform":
                database_key = config.transform.database
            else:
                raise ValueError(f"Unknown db type: {db_type}")
        else:
            # Backwards-compatible path for tests that pass a raw dict
            if db_type == "monitor":
                database_key = config.get("monitor", {}).get("sync", {}).get("database", "wks.monitor")
            elif db_type == "vault":
                database_key = config.get("vault", {}).get("database", "wks.vault")
            elif db_type == "transform":
                database_key = config.get("transform", {}).get("database", "wks.transform")
            else:
                raise ValueError(f"Unknown db type: {db_type}")

        return db_query(database_key, query, limit, projection={"_id": 0})


def call_tool(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Call an MCP tool programmatically (for CLI use).

    This allows CLI to use MCP tools as the source of truth, ensuring
    zero duplication between CLI and MCP interfaces.

    MCP tools return structured MCPResult dictionaries with:
    - success: bool
    - data: dict (actual result data)
    - messages: list of structured messages (errors, warnings, info, status)
    - log: optional list of log entries

    Args:
        tool_name: Name of the tool to call (e.g., "wksm_transform")
        arguments: Tool arguments as a dictionary

    Returns:
        MCPResult as a dictionary with success, data, messages, and optionally log

    Raises:
        KeyError: If tool name is not found
        ValueError: If required parameters are missing (from tool validation)
    """
    config_obj = WKSConfig.load()
    server = MCPServer()
    registry = server._build_tool_registry()

    if tool_name not in registry:
        from .mcp.result import MCPResult

        error_result = MCPResult.error_result(f"Tool not found: {tool_name}", data={})
        return error_result.to_dict()

    handler = registry[tool_name]
    return handler(config_obj, arguments)


def main() -> None:
    """Main entry point for MCP server."""
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
