# Monitor Tools Typer/Pydantic Migration

**Campaign Date:** 2025-12-04
**Status:** PLANNING
**Branch:** `2025-12-04_monitor-typer-migration`

---

## Overview

Migrate all monitor-related tools to use Typer for CLI and Pydantic for validation, eliminating the three parallel layers (MCP schema, CLI argparse, business logic) in favor of a single Python function signature as the source of truth.

## Scope

**In Scope:**
- All monitor MCP tools: `wksm_monitor_status`, `wksm_monitor_check`, `wksm_monitor_validate`, `wksm_monitor_list`, `wksm_monitor_add`, `wksm_monitor_remove`, `wksm_monitor_managed_list`, `wksm_monitor_managed_add`, `wksm_monitor_managed_remove`, `wksm_monitor_managed_set_priority`
- All monitor CLI commands: `wksc monitor status`, `wksc monitor check`, `wksc monitor validate`, `wksc monitor <list>/list`, `wksc monitor <list>/add`, `wksc monitor <list>/remove`, `wksc monitor managed/list`, `wksc monitor managed/add`, `wksc monitor managed/remove`, `wksc monitor managed/set-priority`

**Out of Scope:**
- Transform, diff, vault, service, db, and config tools (will remain as-is for now)
- MCP server infrastructure (JSON-RPC handling, stdio transport)

## Architecture Changes

### Current State
- **MCP Layer**: Manual schema definitions in `MCPServer._define_monitor_*_tools()` methods
- **CLI Layer**: Manual argparse setup in `_setup_monitor()` and `_cmd_monitor_*()` wrapper functions
- **Business Logic**: `MonitorController` static methods

### Target State
- **Single Source**: Python functions with Typer decorators and Pydantic models
- **Auto-Generated CLI**: Typer automatically creates CLI from function signatures
- **Auto-Generated MCP Schema**: Adapter introspects Typer commands to generate MCP JSON schemas
- **Config Injection**: Wrapper/decorator loads config and injects it into functions

## Implementation Plan

### Phase 1: Infrastructure Setup

1. **Add dependencies** (`pyproject.toml`)
   - Add `typer` and `pydantic` to `project.dependencies` list
   - Verify installation works

2. **Create `wks/api/` module structure**
   - `wks/api/__init__.py` - Module initialization
   - `wks/api/monitor.py` - Monitor tool functions with Typer decorators
   - `wks/api/base.py` - Base utilities (config injection decorator, MCP adapter utilities, display output decorator)

3. **Create config injection decorator** (`wks/api/base.py`)
   - Decorator that loads config and injects it as first parameter
   - Handles both dict config (from load_config) and WKSConfig dataclass
   - Can be applied to Typer command functions

4. **Create display output decorator** (`wks/api/base.py`)
   - Decorator that handles return value vs print duality
   - When called via CLI (Typer): Captures return value and prints using display.json_output
   - When called via MCP (direct import): Returns raw MCPResult/dict without printing
   - Uses context detection to determine call path

5. **Create MCP adapter utilities** (`wks/api/base.py`)
   - Function to introspect Typer command and generate MCP JSON schema
   - Uses Pydantic's `TypeAdapter.json_schema()` for type conversion
   - Handles enum types, optional parameters, defaults
   - Extracts descriptions from Pydantic `Field(..., description="...")` and function docstrings
   - Maps to MCP's inputSchema format correctly

### Phase 2: Migrate Monitor Tools

6. **Create Pydantic models for monitor inputs** (`wks/api/monitor.py`)
   - `MonitorListName` - Enum for list names (include_paths, exclude_paths, etc.)
   - `MonitorDirection` - If needed for future use
   - Input models for complex parameters
   - Use `Field(..., description="...")` for all parameter descriptions

7. **Define monitor tool functions** (`wks/api/monitor.py`)
   - Convert each `_tool_monitor_*` handler to a standalone function
   - Use `@app.command()` decorator from Typer
   - Use Pydantic models with `Field(..., description="...")` for parameter descriptions
   - Apply config injection decorator
   - **Return MCPResult/dict, do NOT print** - functions must return structured data
   - Functions should be callable both via Typer CLI and direct Python import (for MCP)

8. **Create Typer app instance** (`wks/api/monitor.py`)
   - `monitor_app = typer.Typer()` for monitor subcommands
   - Register all monitor commands

### Phase 3: Update MCP Server

9. **Create MCP adapter for Typer commands** (`wks/mcp_server.py`)
   - New method `_get_typer_tools_schema()` that introspects `wks.api.monitor.monitor_app`
   - Generates MCP tool schemas from Typer command signatures
   - Maps function names to MCP tool names (e.g., `monitor_status` → `wksm_monitor_status`)

10. **Update `_define_monitor_tools()`** (`wks/mcp_server.py`)
    - Replace manual schema definitions with calls to `_get_typer_tools_schema()`
    - Keep backward compatibility during transition

11. **Update `_build_tool_registry()`** (`wks/mcp_server.py`)
    - Replace manual lambda handlers with calls to Typer command functions
    - Handle argument extraction from MCP JSON-RPC params
    - Wrap return values in MCPResult format

12. **Update `_handle_call_tool()`** (`wks/mcp_server.py`)
    - Route monitor tool calls to Typer command functions
    - Maintain existing error handling and response format

### Phase 4: Update CLI

13. **Integrate Typer app into CLI** (`wks/cli/__init__.py`)
    - Import `monitor_app` from `wks.api.monitor`
    - Replace `_setup_monitor()` with argparse bridge to Typer
    - **Critical**: Use `nargs=argparse.REMAINDER` to capture all remaining arguments
    - Create `_bridge_to_typer()` function that:
      - Extracts remaining args from argparse namespace
      - Invokes `monitor_app(args=args.rest, standalone_mode=False)`
      - Handles display argument integration
    - Apply display output decorator at CLI entry point to print results

14. **Remove old monitor CLI code** (`wks/cli/__init__.py`)
    - Remove `_cmd_monitor_*` wrapper functions
    - Remove old `_setup_monitor()` function (replace with bridge)
    - Keep display argument handling (integrate with Typer bridge)

### Phase 5: Testing & Validation

15. **Update tests**
    - **MCP Tests**: Import functions directly from `wks.api.monitor` and call them
      - Verify return values are correct MCPResult/dict structures
      - Check `success`, `data`, `messages` fields
      - Bypass stdout capturing (functions don't print)
    - **CLI Tests**: Use `typer.testing.CliRunner` for CLI integration tests
      - Test command parsing and execution
      - Verify output formatting via display system
    - Update `test_mcp_server.py` to test new Typer-based tools
    - Create or update `test_cli_monitor.py` for CLI-specific tests
    - Ensure all monitor tool tests pass

16. **Integration testing**
    - Test CLI commands: `wksc monitor status`, `wksc monitor check <path>`, etc.
    - Test MCP tools via `call_tool()` function
    - Verify backward compatibility

### Phase 6: Cleanup

17. **Remove obsolete code**
    - Remove `_define_monitor_*_tools()` static methods from `MCPServer`
    - Remove old `_tool_monitor_*` handler methods (if not used elsewhere)
    - Clean up any unused imports

## Key Files to Modify

- `pyproject.toml` - Add typer and pydantic dependencies
- `wks/api/base.py` (new) - Infrastructure (config decorator, MCP adapter, display decorator)
- `wks/api/monitor.py` (new) - Monitor tool functions with Typer
- `wks/mcp_server.py` - Update to use Typer tools
- `wks/cli/__init__.py` - Replace argparse with Typer integration via bridge
- `tests/test_mcp_server.py` - Update tests
- `tests/test_cli_*.py` - Update CLI tests

## Key Design Decisions

1. **Config Injection**: Use decorator pattern to inject config, keeping function signatures clean
2. **MCPResult Preservation**: Continue returning MCPResult structures for consistency
3. **Incremental Migration**: Only monitor tools migrate; other tools remain unchanged
4. **Backward Compatibility**: MCP tool names and CLI command names remain the same
5. **Type Safety**: Use Pydantic models for validation and schema generation
6. **Return vs Print**: Core functions return MCPResult/dict; display decorator handles CLI printing
7. **Argparse + Typer Bridge**: Use `nargs=argparse.REMAINDER` to pass args to Typer without conflicts
8. **Schema Descriptions**: Use Pydantic `Field(..., description="...")` for MCP inputSchema descriptions

## Technical Considerations

### CLI Integration Strategy
- **Problem**: Both argparse and Typer want to parse `sys.argv`, causing conflicts
- **Solution**: Use `nargs=argparse.REMAINDER` in argparse to capture all remaining arguments and pass them to Typer via `monitor_app(args=args.rest, standalone_mode=False)`

### Return Value vs Print Duality
- **Problem**: Typer commands typically print() and return None, but MCP needs structured return values
- **Solution**:
  - Core functions return MCPResult/dict (no printing)
  - Display decorator at CLI entry point captures return value and prints using display.json_output
  - MCP calls functions directly (bypassing decorator) to get raw return values

### MCP Schema Generation
- Use Pydantic `Field(..., description="...")` for all parameter descriptions
- Extract descriptions from function docstrings as fallback
- Use `TypeAdapter.json_schema()` for type conversion
- Handle enum types, optional parameters, and defaults correctly

### Testing Strategy
- **MCP Tests**: Import and call functions directly, verify return structure
- **CLI Tests**: Use `typer.testing.CliRunner` for integration testing
- Test both paths (CLI and MCP) separately

## Success Criteria

- All monitor CLI commands work identically to before
- All monitor MCP tools work identically to before
- Zero code duplication between CLI and MCP definitions
- Type hints and Pydantic models provide validation
- Tests pass
- Code complexity reduced (fewer manual schema definitions)
- Dependencies added to pyproject.toml
- Argparse + Typer bridge works correctly
- Display decorator handles CLI output properly

## Implementation Todos

1. Add typer and pydantic to pyproject.toml dependencies
2. Create wks/api/ module structure with __init__.py, base.py, and monitor.py
3. Create config injection decorator in wks/api/base.py
4. Create display output decorator in wks/api/base.py
5. Create MCP adapter utilities to introspect Typer commands and generate JSON schemas
6. Create Pydantic models for monitor inputs (MonitorListName enum, etc.) in wks/api/monitor.py
7. Define all monitor tool functions with Typer decorators in wks/api/monitor.py
8. Create Typer app instance and register all monitor commands in wks/api/monitor.py
9. Update MCPServer._define_monitor_tools() to use Typer introspection instead of manual schemas
10. Update MCPServer._build_tool_registry() to route monitor tools to Typer functions
11. Update MCPServer._handle_call_tool() to handle Typer-based monitor tools
12. Integrate monitor Typer app into CLI main() function, replacing _setup_monitor() with bridge
13. Remove old _cmd_monitor_* functions and _setup_monitor() from wks/cli/__init__.py
14. Update tests for monitor tools to work with new Typer-based implementation
15. Remove obsolete _define_monitor_*_tools() methods and old _tool_monitor_* handlers from MCPServer
