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

from .config import WKSConfig
from .mcp.result import MCPResult
from .monitor import MonitorController
from .service_controller import ServiceController
from .vault import VaultController
from .vault.status_controller import VaultStatusController


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
        """Define basic monitor tools (status, check, validate).

        Returns:
            Dictionary of basic monitor tool definitions
        """
        return {
            "wksm_monitor_status": {
                "description": "Get filesystem monitoring status and configuration",
                "inputSchema": {"type": "object", "properties": {}, "required": []},
            },
            "wksm_monitor_check": {
                "description": "Check if a path would be monitored and calculate its priority",
                "inputSchema": {
                    "type": "object",
                    "properties": {"path": {"type": "string", "description": "File or directory path to check"}},
                    "required": ["path"],
                },
            },
            "wksm_monitor_validate": {
                "description": "Validate monitor configuration for conflicts and issues",
                "inputSchema": {"type": "object", "properties": {}, "required": []},
            },
        }

    @staticmethod
    def _define_monitor_list_tools() -> dict[str, dict[str, Any]]:
        """Define monitor list management tools.

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
            "wksm_monitor_list": {
                "description": (
                    "Get contents of a monitor configuration list (include/exclude paths, dirnames, or globs)"
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "list_name": {
                            "type": "string",
                            "description": "Name of the list to retrieve",
                            "enum": list_name_enum,
                        }
                    },
                    "required": ["list_name"],
                },
            },
            "wksm_monitor_add": {
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
            "wksm_monitor_remove": {
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
        """Define monitor managed directory tools.

        Returns:
            Dictionary of managed directory tool definitions
        """
        return {
            "wksm_monitor_managed_list": {
                "description": "Get all managed directories with their priorities",
                "inputSchema": {"type": "object", "properties": {}, "required": []},
            },
            "wksm_monitor_managed_add": {
                "description": "Add a managed directory with priority",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Directory path to add"},
                        "priority": {
                            "type": "integer",
                            "description": "Priority score (higher = more important)",
                        },
                    },
                    "required": ["path", "priority"],
                },
            },
            "wksm_monitor_managed_remove": {
                "description": "Remove a managed directory",
                "inputSchema": {
                    "type": "object",
                    "properties": {"path": {"type": "string", "description": "Directory path to remove"}},
                    "required": ["path"],
                },
            },
            "wksm_monitor_managed_set_priority": {
                "description": "Update priority for a managed directory",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Directory path"},
                        "priority": {"type": "integer", "description": "New priority score"},
                    },
                    "required": ["path", "priority"],
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

    def _build_tool_registry(self) -> dict[str, Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]]:
        """Build registry of tool handlers with parameter validation."""

        def _require_params(
            *param_names: str,
        ) -> Callable[
            [Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]],
            Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]],
        ]:
            """Decorator to validate required parameters."""

            def decorator(
                handler: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]],
            ) -> Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]:
                def wrapper(config: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
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
            "wksm_monitor_status": lambda config, args: self._tool_monitor_status(config),  # noqa: ARG005
            "wksm_monitor_check": _require_params("path")(
                lambda config, args: self._tool_monitor_check(config, args["path"])
            ),
            "wksm_monitor_validate": lambda config, args: self._tool_monitor_validate(config),  # noqa: ARG005
            "wksm_monitor_list": _require_params("list_name")(
                lambda config, args: self._tool_monitor_list(config, args["list_name"])
            ),
            "wksm_monitor_add": _require_params("list_name", "value")(
                lambda config, args: self._tool_monitor_add(config, args["list_name"], args["value"])
            ),
            "wksm_monitor_remove": _require_params("list_name", "value")(
                lambda config, args: self._tool_monitor_remove(config, args["list_name"], args["value"])
            ),
            "wksm_monitor_managed_list": lambda config, args: self._tool_monitor_managed_list(config),  # noqa: ARG005
            "wksm_monitor_managed_add": _require_params("path", "priority")(
                lambda config, args: self._tool_monitor_managed_add(config, args["path"], args["priority"])
            ),
            "wksm_monitor_managed_remove": _require_params("path")(
                lambda config, args: self._tool_monitor_managed_remove(config, args["path"])
            ),
            "wksm_monitor_managed_set_priority": _require_params("path", "priority")(
                lambda config, args: self._tool_monitor_managed_set_priority(config, args["path"], args["priority"])
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

    def _tool_service(self, config: dict[str, Any]) -> dict[str, Any]:  # noqa: ARG002
        """Execute wksm_service tool."""
        status = ServiceController.get_status()
        result = MCPResult.success_result(
            status.to_dict(),
            "Service status retrieved successfully",
        )
        return result.to_dict()

    def _tool_monitor_status(self, config: WKSConfig) -> dict[str, Any]:
        """Execute wks_monitor_status tool."""
        status = MonitorController.get_status(config.monitor)
        return status.model_dump()

    def _tool_monitor_check(self, config: WKSConfig, path: str) -> dict[str, Any]:
        """Execute wks_monitor_check tool."""
        return MonitorController.check_path(config.monitor, path)

    def _tool_monitor_validate(self, config: WKSConfig) -> dict[str, Any]:
        """Execute wks_monitor_validate tool."""
        result = MonitorController.validate_config(config.monitor)
        return result.model_dump()

    def _tool_monitor_list(self, config: WKSConfig, list_name: str) -> dict[str, Any]:
        """Execute wks_monitor_list tool."""
        return MonitorController.get_list(config.monitor, list_name)

    def _tool_monitor_add(self, config: WKSConfig, list_name: str, value: str) -> dict[str, Any]:
        """Execute wks_monitor_add tool."""
        # Determine if we need to resolve paths
        resolve_path = list_name in ["include_paths", "exclude_paths"]

        # Add to list
        result_obj = MonitorController.add_to_list(config.monitor, list_name, value, resolve_path)
        result = result_obj.model_dump()

        # Save if successful
        if result.get("success"):
            config.save()
            result["note"] = "Restart the monitor service for changes to take effect"

        return result

    def _tool_monitor_remove(self, config: WKSConfig, list_name: str, value: str) -> dict[str, Any]:
        """Execute wks_monitor_remove tool."""
        # Determine if we need to resolve paths
        resolve_path = list_name in ["include_paths", "exclude_paths"]

        # Remove from list
        result_obj = MonitorController.remove_from_list(config.monitor, list_name, value, resolve_path)
        result = result_obj.model_dump()

        # Save if successful
        if result.get("success"):
            config.save()
            result["note"] = "Restart the monitor service for changes to take effect"

        return result

    def _tool_monitor_managed_list(self, config: WKSConfig) -> dict[str, Any]:
        """Execute wks_monitor_managed_list tool."""
        result = MonitorController.get_managed_directories(config.monitor)
        return result.model_dump()

    def _tool_monitor_managed_add(self, config: WKSConfig, path: str, priority: int) -> dict[str, Any]:
        """Execute wks_monitor_managed_add tool."""
        # Add managed directory
        result = MonitorController.add_managed_directory(config.monitor, path, priority)

        # Save if successful
        if result.get("success"):
            config.save()
            result["note"] = "Restart the monitor service for changes to take effect"

        return result

    def _tool_monitor_managed_remove(self, config: WKSConfig, path: str) -> dict[str, Any]:
        """Execute wks_monitor_managed_remove tool."""
        # Remove managed directory
        result = MonitorController.remove_managed_directory(config.monitor, path)

        # Save if successful
        if result.get("success"):
            config.save()
            result["note"] = "Restart the monitor service for changes to take effect"

        return result

    def _tool_monitor_managed_set_priority(self, config: WKSConfig, path: str, priority: int) -> dict[str, Any]:
        """Execute wks_monitor_managed_set_priority tool."""
        # Set priority
        result = MonitorController.set_managed_priority(config.monitor, path, priority)

        # Save if successful
        if result.get("success"):
            config.save()
            result["note"] = "Restart the monitor service for changes to take effect"

        return result

    def _tool_vault_status(self, config: WKSConfig) -> dict[str, Any]:
        """Execute wks_vault_status tool."""
        # Legacy controller expects dict
        controller = VaultStatusController(config.to_dict())
        summary = controller.summarize()
        return summary.to_dict()

    def _tool_vault_sync(self, config: WKSConfig, batch_size: int) -> dict[str, Any]:
        """Execute wks_vault_sync tool."""
        # Legacy controller expects dict
        return VaultController.sync_vault(config.to_dict(), batch_size)

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
            monitor_info = MonitorController.check_path(config.monitor, str(file_path_expanded))
            is_monitored = monitor_info.get("is_monitored", False)
            priority = monitor_info.get("priority", 0) if is_monitored else None
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

    def _tool_config(self, config: WKSConfig) -> dict[str, Any]:
        """Execute wksm_config tool."""
        result = MCPResult(success=True, data=config.to_dict())
        result.add_success("Configuration loaded successfully")
        return result.to_dict()

    def _tool_transform(
        self,
        config: WKSConfig,
        file_path: str,
        engine: str,
        options: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute wksm_transform tool."""
        from pathlib import Path

        from .db_helpers import connect_to_mongo
        from .transform import TransformController
        from .utils import expand_path

        result = MCPResult(success=False, data={})

        try:
            # Validate file exists
            path = expand_path(file_path)
            if not path.exists():
                return result.error_result(f"File not found: {path}", data={}).to_dict()

            # Use passed config
            cache_location = Path(config.transform.cache.location).expanduser()
            max_size_bytes = config.transform.cache.max_size_bytes

            from pymongo import MongoClient

            uri = config.mongo.uri
            db_name = config.transform.database.split(".")[0]

            client: MongoClient = connect_to_mongo(uri)
            db = client[db_name]

            controller = TransformController(db, cache_location, max_size_bytes)

            # Transform
            result.add_status(f"Transforming {path.name} using {engine}...")
            cache_key = controller.transform(path, engine, options)

            client.close()

            return result.success_result({"checksum": cache_key}, "Transform completed successfully").to_dict()

        except ValueError as e:
            return result.error_result(f"Invalid input: {e!s}", data={}).to_dict()
        except RuntimeError as e:
            return result.error_result(f"Transform failed: {e!s}", data={}).to_dict()
        except Exception as e:
            return result.error_result(f"Unexpected error: {e!s}", details=str(e), data={}).to_dict()

    def _tool_cat(self, config: WKSConfig, target: str) -> dict[str, Any]:
        """Execute wksm_cat tool."""
        from pathlib import Path

        from .db_helpers import connect_to_mongo
        from .transform import TransformController

        result = MCPResult(success=False, data={})

        try:
            # Use passed config
            cache_location = Path(config.transform.cache.location).expanduser()
            max_size_bytes = config.transform.cache.max_size_bytes

            from pymongo import MongoClient

            uri = config.mongo.uri
            db_name = config.transform.database.split(".")[0]

            client: MongoClient = connect_to_mongo(uri)
            db = client[db_name]

            controller = TransformController(db, cache_location, max_size_bytes)

            # Get content
            content = controller.get_content(target)

            client.close()

            return result.success_result({"content": content}, "Content retrieved successfully").to_dict()

        except FileNotFoundError as e:
            return result.error_result(f"File or cache entry not found: {target}", details=str(e), data={}).to_dict()
        except Exception as e:
            return result.error_result(f"Failed to retrieve content: {e!s}", details=str(e), data={}).to_dict()

    def _tool_diff(self, config: WKSConfig, engine: str, target_a: str, target_b: str) -> dict[str, Any]:
        """Execute wksm_diff tool."""
        from pathlib import Path

        from .db_helpers import connect_to_mongo
        from .diff import DiffController
        from .diff.config import DiffConfig, DiffConfigError
        from .transform import TransformController

        result = MCPResult(success=False, data={})

        try:
            # Setup transform controller for checksum resolution
            transform_cfg = config.transform
            cache_location = Path(transform_cfg.cache.location).expanduser()
            max_size_bytes = transform_cfg.cache.max_size_bytes

            from pymongo import MongoClient

            uri = config.mongo.uri
            db_name = transform_cfg.database.split(".")[0]

            client: MongoClient = connect_to_mongo(uri)
            db = client[db_name]

            transform_controller = TransformController(db, cache_location, max_size_bytes)

            # Load diff configuration and construct controller when available.
            # DiffConfig currently expects dict in from_config_dict
            # We should convert WKSConfig back to dict for legacy compatibility if needed
            # or update DiffConfig to support WKSConfig.
            # For now, let's convert config to dict for DiffConfig.
            config_dict = config.to_dict()
            try:
                diff_config = DiffConfig.from_config_dict(config_dict)
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

    def _tool_vault_validate(self, config: WKSConfig) -> dict[str, Any]:
        """Execute wks_vault_validate tool."""
        from .vault import VaultController, load_vault

        # Legacy helpers expect dict
        vault = load_vault(config.to_dict())
        controller = VaultController(vault)
        return controller.validate_vault()

    def _tool_vault_fix_symlinks(self, config: WKSConfig) -> dict[str, Any]:
        """Execute wks_vault_fix_symlinks tool."""
        from .vault import VaultController, load_vault

        # Legacy helpers expect dict
        vault = load_vault(config.to_dict())
        controller = VaultController(vault)
        result = controller.fix_symlinks()

        # Convert dataclass to dict
        return {
            "notes_scanned": result.notes_scanned,
            "links_found": result.links_found,
            "created": result.created,
            "failed": result.failed,
        }

    def _tool_db_query(self, config: WKSConfig, db_type: str, query: dict[str, Any], limit: int) -> dict[str, Any]:
        """Execute wks_db_* tools."""
        from .db_helpers import connect_to_mongo

        uri = config.mongo.uri

        if db_type == "monitor":
            db_name = config.monitor.database.split(".")[0]
            coll_name = config.monitor.database.split(".")[1]
        elif db_type == "vault":
            db_name = config.vault.database.split(".")[0]
            coll_name = config.vault.database.split(".")[1]
        elif db_type == "transform":
            db_name = config.transform.database.split(".")[0]
            coll_name = config.transform.database.split(".")[1]
        else:
            raise ValueError(f"Unknown db type: {db_type}")

        from pymongo import MongoClient

        client: MongoClient = connect_to_mongo(uri)
        coll = client[db_name][coll_name]

        results = list(coll.find(query, {"_id": 0}).limit(limit))

        client.close()
        return {"results": results, "count": len(results)}


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
