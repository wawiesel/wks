# MCP Layer

The MCP (Model Context Protocol) layer provides a JSON-RPC interface for WKS functionality, enabling AI agents and other tools to interact with WKS programmatically. The MCP functionality is identical to the CLI functionality - both get all information from the API layer. You only need to change things in one place (the API) to propagate to both CLI and MCP.

## Architecture

The MCP layer follows the same API-first design principle as the CLI:

```
┌─────────────────┐
│   MCP Client    │  (AI Agent, Claude Desktop, etc.)
└────────┬────────┘
         │ JSON-RPC over stdio
         ▼
┌─────────────────┐
│   MCPServer     │  (wks/mcp/server.py)
│  - Auto-Discovery│
│  - Tool Registry│
│  - Schema Gen   │
└────────┬────────┘
         │ Calls API functions
         ▼
┌─────────────────┐
│   API Layer     │  (wks/api/*/cmd_*.py)
│  - Business Logic│
│  - StageResult   │
└─────────────────┘
```

**Key Principles:**
- **Zero Duplication**: MCP and CLI call the exact same API functions
- **Automatic Discovery**: All directories in `wks/api/` that don't start with `_` are automatically discovered and enabled in MCP
- **Zero Configuration**: No changes needed to MCP or CLI layers when adding new API capabilities - it's automatic
- **Typer Introspection**: MCP tool schemas are automatically generated from Typer command definitions
- **Structured Output**: All tools return `MCPResult` objects with consistent structure
- **Pure API Layer**: The API layer contains only business logic - no display or formatting code

## Mandatory Rule: Automatic Discovery

**MANDATORY RULE**: No changes need to be made to the MCP (or CLI) layers at `wks/mcp` and `wks/cli` to enable new API capabilities. It is automatically handled as they are added. Any directory in `wks/api/` that doesn't start with underscore is automatically discovered and exposed.

The MCP server automatically:
1. Scans all directories in `wks/api/` that don't start with `_`
2. Discovers all `cmd_*.py` files in those directories
3. Finds the corresponding Typer app (trying common naming patterns like `{domain}_app`, `db_app`, etc.)
4. Generates tool schemas using Typer introspection
5. Creates tool handlers that call the API functions
6. Exposes them as `wksm_{domain}_{command}` tools

This means adding a new API capability requires **zero changes** to `wks/mcp/server.py` or any CLI code. Simply create the API function and register it in the Typer app, and it's automatically available in both CLI and MCP.

## Components

### `server.py` - MCP Server Implementation

The main MCP server that:
- Handles JSON-RPC requests over stdio
- Maintains a tool registry mapping tool names to API functions
- Generates tool schemas using Typer introspection
- Converts `StageResult` objects to `MCPResult` responses

**Key Methods:**
- `_define_tools()`: Defines all available MCP tools and their schemas
- `_build_tool_registry()`: Maps tool names to handler functions that call API functions
- `_handle_call_tool()`: Processes tool call requests and returns results

**Tool Naming Convention:**
- MCP tools follow the pattern: `wksm_<domain>_<command>`
- Example: `wksm_config` (config domain, show command), `wksm_monitor_status` (monitor domain, status command)

### `result.py` - MCP Result Types

Defines structured result types for MCP responses:
- `MCPResult`: Main result container with `success`, `data`, `messages`, and optional `log`
- `Message`: Structured message with `type`, `content`, and `timestamp`
- `MessageType`: Enum for message types (error, warning, info, status)

### `display.py` - MCP Display Implementation

Implements the `Display` interface for MCP, outputting JSON-formatted messages to stdout. Used internally by API functions when called in MCP context.

### `paths.py` - MCP Socket Paths

Utilities for MCP socket locations:
- `mcp_socket_path()`: Returns the canonical MCP broker socket path (`{WKS_HOME}/mcp.sock`)

### `setup.py` - MCP Installation

Functions for installing WKS MCP server configurations into various MCP client applications (Claude Desktop, Gemini, etc.).

### `bridge.py` - MCP Broker

MCP broker implementation for managing multiple MCP connections.

### `client.py` - MCP Client Utilities

Utilities for MCP client operations, including stdio-to-socket proxying.

## How It Works

### 1. Tool Definition

Tools are defined in `MCPServer._define_tools()` using one of two approaches:

**A. Typer Introspection (Preferred)**
For commands that have Typer apps, schemas are automatically extracted:

```python
from wks.api.monitor import monitor_app
schema = get_typer_command_schema(monitor_app, "status")
tools["wksm_monitor_status"] = {
    "description": "Get monitor status",
    "inputSchema": schema,
}
```

**B. Manual Schema Definition**
For legacy or special tools, schemas are defined manually:

```python
tools["wksm_transform"] = {
    "description": "Transform a file using a specific engine",
    "inputSchema": {
        "type": "object",
        "properties": {
            "file_path": {"type": "string"},
            "engine": {"type": "string"},
        },
        "required": ["file_path", "engine"],
    },
}
```

### 2. Tool Registry

The tool registry (`_build_tool_registry()`) maps tool names to handler functions that:
1. Extract arguments from the MCP request
2. Call the corresponding API function
3. Convert `StageResult` to `MCPResult`
4. Return structured JSON response

Example:
```python
"wksm_config": lambda config, args: MCPResult(
    success=True,
    data=_extract_data_from_stage_result(cmd_show(section=args.get("section", "") or ""))
).to_dict(),
```

### 3. Request Handling

When an MCP client calls a tool:
1. `_handle_call_tool()` receives the JSON-RPC request
2. Looks up the tool in the registry
3. Validates required parameters (if using `_require_params` decorator)
4. Calls the handler function with config and arguments
5. Returns `MCPResult` as JSON-RPC response

### 4. Schema Generation

For Typer-based commands, `get_typer_command_schema()` introspects the Typer app to extract:
- Parameter names and types
- Required vs optional parameters
- Help text from Typer annotations
- Union types (e.g., `str | None`)

This ensures MCP tools automatically stay in sync with CLI command signatures.

## Adding New Tools

**AUTOMATIC - NO MCP/CLI CHANGES NEEDED**

To add a new MCP tool, you only need to:

### Step 1: Create API Function

Create the API function in `wks/api/<domain>/cmd_<name>.py` (where `<domain>` is a directory that doesn't start with `_`):

```python
from ..StageResult import StageResult

def cmd_<name>(param1: str, param2: int = 0) -> StageResult:
    """Command description."""
    # ... business logic ...
    return StageResult(
        announce="Starting...",
        progress_callback=do_work,
    )
```

### Step 2: Register in Typer App

Register the command in `wks/api/<domain>/app.py`:

```python
from .cmd_<name> import cmd_<name>

@<domain>_app.command(name="<name>")
def <name>_command(ctx: typer.Context, param1: str, param2: int = 0) -> None:
    """Command description."""
    wrapped = handle_stage_result(cmd_<name>)
    wrapped(param1, param2)
```

### Step 3: Done!

The MCP server automatically:
- Discovers the `cmd_<name>` function
- Finds the Typer app for the domain
- Generates the schema from Typer introspection
- Creates the tool handler
- Exposes it as `wksm_<domain>_<name>`

**No changes to `wks/mcp/server.py` or `wks/cli/` are needed!**

### Testing

Test the tool using an MCP client or the `call_tool()` function:
```python
from wks.mcp.call_tool import call_tool
result = call_tool("wksm_<domain>_<name>", {"param1": "value", "param2": 42})
```

## File Structure

- **`server.py`**: Main MCP server implementation, tool definitions, and registry
- **`result.py`**: `MCPResult`, `Message`, and `MessageType` definitions
- **`display.py`**: `MCPDisplay` class for JSON-formatted output
- **`paths.py`**: Utilities for MCP socket paths
- **`setup.py`**: Functions for installing MCP server configurations
- **`bridge.py`**: MCP broker for managing multiple connections
- **`client.py`**: MCP client utilities and stdio proxying
- **`__init__.py`**: Module exports

## CLI/MCP Symmetry

Every CLI command has a corresponding MCP tool:
- `wksc config` → `wksm_config`
- `wksc monitor status` → `wksm_monitor_status`
- `wksc database list` → `wksm_database_list`

Both interfaces:
- Call the same API functions
- Use the same business logic
- Return the same data (different presentation)
- Share the same validation and error handling

This ensures consistency and eliminates duplication - changes to API functions automatically propagate to both CLI and MCP.

## Output Structure

All MCP tools return `MCPResult` objects with this structure:

```json
{
  "success": true,
  "data": { ... },
  "messages": [
    {
      "type": "info",
      "content": "Message text",
      "timestamp": "2025-01-01T00:00:00Z"
    }
  ],
  "log": [ ... ]  // Optional
}
```

The `data` field contains the `output` from the `StageResult` returned by the API function, ensuring consistent structure across all tools.
