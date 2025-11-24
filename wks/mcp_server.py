"""
MCP Server for WKS - Model Context Protocol integration.

Exposes WKS functionality as MCP tools via stdio transport.
Uses existing controllers for zero code duplication per SPEC.md.
"""

import json
import sys
from typing import Any, Dict, List, Optional, TextIO

from .config import load_config
from .monitor import MonitorController
from .vault import VaultController


class MCPServer:
    """MCP server exposing WKS tools via stdio."""

    def __init__(
        self,
        *,
        input_stream: Optional[TextIO] = None,
        output_stream: Optional[TextIO] = None,
    ):
        """Initialize MCP server."""
        self._input = input_stream or sys.stdin
        self._output = output_stream or sys.stdout
        self._lsp_mode = False
        self.tools = {
            "wks_monitor_status": {
                "description": "Get filesystem monitoring status and configuration",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            "wks_monitor_check": {
                "description": "Check if a path would be monitored and calculate its priority",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "File or directory path to check"
                        }
                    },
                    "required": ["path"]
                }
            },
            "wks_monitor_validate": {
                "description": "Validate monitor configuration for conflicts and issues",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            "wks_monitor_list": {
                "description": "Get contents of a monitor configuration list (include/exclude paths, dirnames, or globs)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "list_name": {
                            "type": "string",
                            "description": "Name of the list to retrieve",
                            "enum": ["include_paths", "exclude_paths", "include_dirnames", "exclude_dirnames", "include_globs", "exclude_globs"]
                        }
                    },
                    "required": ["list_name"]
                }
            },
            "wks_monitor_add": {
                "description": "Add a value to a monitor configuration list",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "list_name": {
                            "type": "string",
                            "description": "Name of the list to modify",
                            "enum": ["include_paths", "exclude_paths", "include_dirnames", "exclude_dirnames", "include_globs", "exclude_globs"]
                        },
                        "value": {
                            "type": "string",
                            "description": "Value to add (path for include/exclude_paths, dirname for include/exclude_dirnames, pattern for include/exclude_globs)"
                        }
                    },
                    "required": ["list_name", "value"]
                }
            },
            "wks_monitor_remove": {
                "description": "Remove a value from a monitor configuration list",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "list_name": {
                            "type": "string",
                            "description": "Name of the list to modify",
                            "enum": ["include_paths", "exclude_paths", "include_dirnames", "exclude_dirnames", "include_globs", "exclude_globs"]
                        },
                        "value": {
                            "type": "string",
                            "description": "Value to remove"
                        }
                    },
                    "required": ["list_name", "value"]
                }
            },
            "wks_monitor_managed_list": {
                "description": "Get all managed directories with their priorities",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            "wks_monitor_managed_add": {
                "description": "Add a managed directory with priority",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Directory path to add"
                        },
                        "priority": {
                            "type": "integer",
                            "description": "Priority score (higher = more important)"
                        }
                    },
                    "required": ["path", "priority"]
                }
            },
            "wks_monitor_managed_remove": {
                "description": "Remove a managed directory",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Directory path to remove"
                        }
                    },
                    "required": ["path"]
                }
            },
            "wks_monitor_managed_set_priority": {
                "description": "Update priority for a managed directory",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Directory path"
                        },
                        "priority": {
                            "type": "integer",
                            "description": "New priority score"
                        }
                    },
                    "required": ["path", "priority"]
                }
            },
            "wks_vault_status": {
                "description": "Get vault link status summary including link counts, issues, and errors",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            "wks_vault_sync": {
                "description": "Sync vault links to MongoDB with optional batch size",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "batch_size": {
                            "type": "integer",
                            "description": "Number of records to process per batch (default 1000)"
                        }
                    },
                    "required": []
                }
            },
            "wks_vault_links": {
                "description": "Get all links to and from a specific vault file",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to the vault file (e.g., ~/_vault/Projects/XYZ.md)"
                        },
                        "direction": {
                            "type": "string",
                            "description": "Link direction filter: 'both' (default), 'to' (incoming only), or 'from' (outgoing only)",
                            "enum": ["both", "to", "from"]
                        }
                    },
                    "required": ["file_path"]
                }
            }
        }
        self.resources = [
            {
                "uri": "mcp://wks/tools",
                "name": "wks-tools",
                "description": "WKS monitor and vault tooling available via tools/call",
                "type": "tool-collection"
            }
        ]

    def _read_message(self) -> Optional[Dict[str, Any]]:
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
                    self._lsp_mode = True
                    try:
                        length = int(stripped.split(":", 1)[1].strip())
                    except Exception:
                        raise ValueError(f"Invalid Content-Length header: {stripped!r}")
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
                else:
                    return json.loads(line)
        except Exception as e:
            sys.stderr.write(f"Parse error: {e}\n")
            return None

    def _write_message(self, message: Dict[str, Any]) -> None:
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
        self._write_message({
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result
        })

    def _write_error(self, request_id: Any, code: int, message: str, data: Any = None) -> None:
        """Write JSON-RPC error response."""
        error = {"code": code, "message": message}
        if data is not None:
            error["data"] = data
        self._write_message({
            "jsonrpc": "2.0",
            "id": request_id,
            "error": error
        })

    def _handle_initialize(self, request_id: Any, params: Dict[str, Any]) -> None:
        """Handle initialize request."""
        self._write_response(request_id, {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {},
                "resources": {}
            },
            "serverInfo": {
                "name": "wks-mcp-server",
                "version": "1.0.0"
            }
        })

    def _handle_list_tools(self, request_id: Any) -> None:
        """Handle tools/list request."""
        tools_list = [
            {
                "name": name,
                "description": info["description"],
                "inputSchema": info["inputSchema"]
            }
            for name, info in self.tools.items()
        ]
        self._write_response(request_id, {"tools": tools_list})

    def _handle_list_resources(self, request_id: Any, params: Dict[str, Any]) -> None:
        """Handle resources/list request with a single static page."""
        if request_id is None:
            return

        # Basic pagination contract—single page only.
        result = {"resources": self.resources}
        if params.get("cursor") is not None:
            result["nextCursor"] = None
        self._write_response(request_id, result)

    def _build_tool_registry(self) -> Dict[str, callable]:
        """Build registry of tool handlers with parameter validation."""
        def _require_params(*param_names: str):
            """Decorator to validate required parameters."""
            def decorator(handler: callable) -> callable:
                def wrapper(config: Dict[str, Any], arguments: Dict[str, Any]) -> Dict[str, Any]:
                    missing = [p for p in param_names if arguments.get(p) is None]
                    if missing:
                        raise ValueError(f"Missing required parameters: {', '.join(missing)}")
                    return handler(config, arguments)
                return wrapper
            return decorator

        return {
            "wks_monitor_status": lambda config, args: self._tool_monitor_status(config),
            "wks_monitor_check": _require_params("path")(
                lambda config, args: self._tool_monitor_check(config, args["path"])
            ),
            "wks_monitor_validate": lambda config, args: self._tool_monitor_validate(config),
            "wks_monitor_list": _require_params("list_name")(
                lambda config, args: self._tool_monitor_list(config, args["list_name"])
            ),
            "wks_monitor_add": _require_params("list_name", "value")(
                lambda config, args: self._tool_monitor_add(config, args["list_name"], args["value"])
            ),
            "wks_monitor_remove": _require_params("list_name", "value")(
                lambda config, args: self._tool_monitor_remove(config, args["list_name"], args["value"])
            ),
            "wks_monitor_managed_list": lambda config, args: self._tool_monitor_managed_list(config),
            "wks_monitor_managed_add": _require_params("path", "priority")(
                lambda config, args: self._tool_monitor_managed_add(config, args["path"], args["priority"])
            ),
            "wks_monitor_managed_remove": _require_params("path")(
                lambda config, args: self._tool_monitor_managed_remove(config, args["path"])
            ),
            "wks_monitor_managed_set_priority": _require_params("path", "priority")(
                lambda config, args: self._tool_monitor_managed_set_priority(config, args["path"], args["priority"])
            ),
            "wks_vault_status": lambda config, args: self._tool_vault_status(config),
            "wks_vault_sync": lambda config, args: self._tool_vault_sync(
                config, args.get("batch_size", 1000)
            ),
            "wks_vault_links": _require_params("file_path")(
                lambda config, args: self._tool_vault_links(
                    config, args["file_path"], args.get("direction", "both")
                )
            ),
        }

    def _handle_call_tool(self, request_id: Any, params: Dict[str, Any]) -> None:
        """Handle tools/call request using registry pattern."""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if tool_name not in self.tools:
            self._write_error(request_id, -32601, f"Tool not found: {tool_name}")
            return

        try:
            config = load_config()
            registry = self._build_tool_registry()

            if tool_name not in registry:
                self._write_error(request_id, -32601, f"Tool not implemented: {tool_name}")
                return

            handler = registry[tool_name]
            result = handler(config, arguments)

            self._write_response(request_id, {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result, indent=2)
                    }
                ]
            })

        except ValueError as e:
            self._write_error(request_id, -32602, str(e))
        except Exception as e:
            self._write_error(request_id, -32000, f"Tool execution failed: {e}", {"traceback": str(e)})

    def _tool_monitor_status(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Execute wks_monitor_status tool."""
        status = MonitorController.get_status(config)
        return status.to_dict()

    def _tool_monitor_check(self, config: Dict[str, Any], path: str) -> Dict[str, Any]:
        """Execute wks_monitor_check tool."""
        return MonitorController.check_path(config, path)

    def _tool_monitor_validate(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Execute wks_monitor_validate tool."""
        return MonitorController.validate_config(config)

    def _tool_monitor_list(self, config: Dict[str, Any], list_name: str) -> Dict[str, Any]:
        """Execute wks_monitor_list tool."""
        return MonitorController.get_list(config, list_name)

    def _tool_monitor_add(self, config: Dict[str, Any], list_name: str, value: str) -> Dict[str, Any]:
        """Execute wks_monitor_add tool."""
        from .config import get_config_path

        config_path = get_config_path()
        if not config_path.exists():
            return {"success": False, "message": f"Config file not found: {config_path}"}

        # Load config from file
        with open(config_path) as f:
            config_dict = json.load(f)

        # Determine if we need to resolve paths
        resolve_path = list_name in ["include_paths", "exclude_paths"]

        # Add to list
        result = MonitorController.add_to_list(config_dict, list_name, value, resolve_path)

        # Save if successful
        if result.get("success"):
            with open(config_path, "w") as f:
                json.dump(config_dict, f, indent=4)
            result["note"] = "Restart the monitor service for changes to take effect"

        return result

    def _tool_monitor_remove(self, config: Dict[str, Any], list_name: str, value: str) -> Dict[str, Any]:
        """Execute wks_monitor_remove tool."""
        from .config import get_config_path

        config_path = get_config_path()
        if not config_path.exists():
            return {"success": False, "message": f"Config file not found: {config_path}"}

        # Load config from file
        with open(config_path) as f:
            config_dict = json.load(f)

        # Determine if we need to resolve paths
        resolve_path = list_name in ["include_paths", "exclude_paths"]

        # Remove from list
        result = MonitorController.remove_from_list(config_dict, list_name, value, resolve_path)

        # Save if successful
        if result.get("success"):
            with open(config_path, "w") as f:
                json.dump(config_dict, f, indent=4)
            result["note"] = "Restart the monitor service for changes to take effect"

        return result

    def _tool_monitor_managed_list(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Execute wks_monitor_managed_list tool."""
        return MonitorController.get_managed_directories(config)

    def _tool_monitor_managed_add(self, config: Dict[str, Any], path: str, priority: int) -> Dict[str, Any]:
        """Execute wks_monitor_managed_add tool."""
        from .config import get_config_path

        config_path = get_config_path()
        if not config_path.exists():
            return {"success": False, "message": f"Config file not found: {config_path}"}

        # Load config from file
        with open(config_path) as f:
            config_dict = json.load(f)

        # Add managed directory
        result = MonitorController.add_managed_directory(config_dict, path, priority)

        # Save if successful
        if result.get("success"):
            with open(config_path, "w") as f:
                json.dump(config_dict, f, indent=4)
            result["note"] = "Restart the monitor service for changes to take effect"

        return result

    def _tool_monitor_managed_remove(self, config: Dict[str, Any], path: str) -> Dict[str, Any]:
        """Execute wks_monitor_managed_remove tool."""
        from .config import get_config_path

        config_path = get_config_path()
        if not config_path.exists():
            return {"success": False, "message": f"Config file not found: {config_path}"}

        # Load config from file
        with open(config_path) as f:
            config_dict = json.load(f)

        # Remove managed directory
        result = MonitorController.remove_managed_directory(config_dict, path)

        # Save if successful
        if result.get("success"):
            with open(config_path, "w") as f:
                json.dump(config_dict, f, indent=4)
            result["note"] = "Restart the monitor service for changes to take effect"

        return result

    def _tool_monitor_managed_set_priority(self, config: Dict[str, Any], path: str, priority: int) -> Dict[str, Any]:
        """Execute wks_monitor_managed_set_priority tool."""
        from .config import get_config_path

        config_path = get_config_path()
        if not config_path.exists():
            return {"success": False, "message": f"Config file not found: {config_path}"}

        # Load config from file
        with open(config_path) as f:
            config_dict = json.load(f)

        # Set priority
        result = MonitorController.set_managed_priority(config_dict, path, priority)

        # Save if successful
        if result.get("success"):
            with open(config_path, "w") as f:
                json.dump(config_dict, f, indent=4)
            result["note"] = "Restart the monitor service for changes to take effect"

        return result

    def _tool_vault_status(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Execute wks_vault_status tool."""
        return VaultController.get_status(config)

    def _tool_vault_sync(self, config: Dict[str, Any], batch_size: int) -> Dict[str, Any]:
        """Execute wks_vault_sync tool."""
        return VaultController.sync_vault(config, batch_size)

    def _tool_vault_links(self, config: Dict[str, Any], file_path: str, direction: str = "both") -> Dict[str, Any]:
        """Execute wks_vault_links tool."""
        from pathlib import Path
        from .utils import expand_path
        from .db_helpers import get_vault_db_config, connect_to_mongo
        from .uri_utils import convert_to_uri

        # Get vault configuration
        vault_cfg = config.get("vault", {})
        vault_path_str = vault_cfg.get("base_dir")
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
            monitor_info = MonitorController.check_path(config, str(file_path_expanded))
            is_monitored = monitor_info.get("is_monitored", False)
            priority = monitor_info.get("priority", 0) if is_monitored else None
        except Exception:
            is_monitored = False
            priority = None

        # Convert to URI using central conversion function
        target_uri = convert_to_uri(file_path_expanded, vault_path)

        # Also get version without .md extension for fallback matching
        if target_uri.endswith('.md'):
            target_uri_no_ext = target_uri[:-3]
        else:
            target_uri_no_ext = target_uri

        # Connect to database
        uri, db_name, coll_name = get_vault_db_config(config)
        client = connect_to_mongo(uri)
        coll = client[db_name][coll_name]

        result = {
            "file": target_uri,
            "is_monitored": is_monitored,
            "priority": priority if is_monitored else None
        }

        # Query for links FROM this file (URI-only, no legacy path fallbacks)
        is_external = not target_uri.startswith("vault://")
        if direction in ("both", "from") and not is_external:
            from_query = {
                "doc_type": "link",
                "$or": [
                    {"from_uri": target_uri},
                    {"from_uri": target_uri_no_ext}
                ]
            }
            links_from = list(coll.find(from_query, {"_id": 0}))
            result["links_from"] = links_from

        # Query for links TO this file (URI-only, no legacy path fallbacks)
        if direction in ("both", "to"):
            to_query = {
                "doc_type": "link",
                "$or": [
                    {"to_uri": target_uri},
                    {"to_uri": target_uri_no_ext}
                ]
            }
            links_to = list(coll.find(to_query, {"_id": 0}))
            result["links_to"] = links_to

        client.close()
        return result

    def run(self) -> None:
        """Run MCP server main loop."""
        while True:
            message = self._read_message()
            if message is None:
                break

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


def main():
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
