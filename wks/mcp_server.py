"""
MCP Server for WKS - Model Context Protocol integration.

Exposes WKS functionality as MCP tools via stdio transport.
Uses existing controllers for zero code duplication per SPEC.md.
"""

import json
import sys
from typing import Any, Dict, List, Optional

from .config import load_config
from .monitor_controller import MonitorController


class MCPServer:
    """MCP server exposing WKS tools via stdio."""

    def __init__(self):
        """Initialize MCP server."""
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
                "description": "Get contents of a monitor configuration list (include_paths, exclude_paths, ignore_dirnames, ignore_globs)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "list_name": {
                            "type": "string",
                            "description": "Name of the list to retrieve",
                            "enum": ["include_paths", "exclude_paths", "ignore_dirnames", "ignore_globs"]
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
                            "enum": ["include_paths", "exclude_paths", "ignore_dirnames", "ignore_globs"]
                        },
                        "value": {
                            "type": "string",
                            "description": "Value to add (path for include/exclude_paths, dirname for ignore_dirnames, pattern for ignore_globs)"
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
                            "enum": ["include_paths", "exclude_paths", "ignore_dirnames", "ignore_globs"]
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
            }
        }

    def _read_message(self) -> Optional[Dict[str, Any]]:
        """Read JSON-RPC message from stdin."""
        try:
            line = sys.stdin.readline()
            if not line:
                return None
            return json.loads(line)
        except Exception as e:
            # Log parse errors to stderr but don't send error response
            # (can't send valid JSON-RPC error without request ID)
            sys.stderr.write(f"Parse error: {e}\n")
            return None

    def _write_message(self, message: Dict[str, Any]) -> None:
        """Write JSON-RPC message to stdout."""
        sys.stdout.write(json.dumps(message) + "\n")
        sys.stdout.flush()

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
                "tools": {}
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

    def _handle_call_tool(self, request_id: Any, params: Dict[str, Any]) -> None:
        """Handle tools/call request."""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if tool_name not in self.tools:
            self._write_error(request_id, -32601, f"Tool not found: {tool_name}")
            return

        try:
            # Load config once per call
            config = load_config()

            # Route to appropriate tool handler
            if tool_name == "wks_monitor_status":
                result = self._tool_monitor_status(config)
            elif tool_name == "wks_monitor_check":
                path = arguments.get("path")
                if not path:
                    self._write_error(request_id, -32602, "Missing required parameter: path")
                    return
                result = self._tool_monitor_check(config, path)
            elif tool_name == "wks_monitor_validate":
                result = self._tool_monitor_validate(config)
            elif tool_name == "wks_monitor_list":
                list_name = arguments.get("list_name")
                if not list_name:
                    self._write_error(request_id, -32602, "Missing required parameter: list_name")
                    return
                result = self._tool_monitor_list(config, list_name)
            elif tool_name == "wks_monitor_add":
                list_name = arguments.get("list_name")
                value = arguments.get("value")
                if not list_name or not value:
                    self._write_error(request_id, -32602, "Missing required parameters: list_name, value")
                    return
                result = self._tool_monitor_add(config, list_name, value)
            elif tool_name == "wks_monitor_remove":
                list_name = arguments.get("list_name")
                value = arguments.get("value")
                if not list_name or not value:
                    self._write_error(request_id, -32602, "Missing required parameters: list_name, value")
                    return
                result = self._tool_monitor_remove(config, list_name, value)
            elif tool_name == "wks_monitor_managed_list":
                result = self._tool_monitor_managed_list(config)
            elif tool_name == "wks_monitor_managed_add":
                path = arguments.get("path")
                priority = arguments.get("priority")
                if not path or priority is None:
                    self._write_error(request_id, -32602, "Missing required parameters: path, priority")
                    return
                result = self._tool_monitor_managed_add(config, path, priority)
            elif tool_name == "wks_monitor_managed_remove":
                path = arguments.get("path")
                if not path:
                    self._write_error(request_id, -32602, "Missing required parameter: path")
                    return
                result = self._tool_monitor_managed_remove(config, path)
            elif tool_name == "wks_monitor_managed_set_priority":
                path = arguments.get("path")
                priority = arguments.get("priority")
                if not path or priority is None:
                    self._write_error(request_id, -32602, "Missing required parameters: path, priority")
                    return
                result = self._tool_monitor_managed_set_priority(config, path, priority)
            else:
                self._write_error(request_id, -32601, f"Tool not implemented: {tool_name}")
                return

            # Return tool result
            self._write_response(request_id, {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result, indent=2)
                    }
                ]
            })

        except Exception as e:
            self._write_error(request_id, -32000, f"Tool execution failed: {e}", {"traceback": str(e)})

    def _tool_monitor_status(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Execute wks_monitor_status tool."""
        return MonitorController.get_status(config)

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
