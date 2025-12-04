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
- **Business Logic**: `MonitorController`, `MonitorOperations`, `MonitorValidator` classes with static methods (just namespaces)
- **Structure**: `wks/monitor/` directory with separate controller/operations/validator files

### Target State
- **Single Source**: Python functions with Typer decorators and Pydantic models
- **One File Per Function Rule**: File name matches function name exactly
  - `wks/api/monitor/get_status.py` - `get_status()` function
  - `wks/api/monitor/check_path.py` - `check_path()` function
  - `wks/api/monitor/validate_config.py` - `validate_config()` function
  - `wks/api/monitor/get_list.py` - `get_list()` function
  - `wks/api/monitor/add_to_list.py` - `add_to_list()` function
  - `wks/api/monitor/remove_from_list.py` - `remove_from_list()` function
  - `wks/api/monitor/get_managed_directories.py` - `get_managed_directories()` function
  - `wks/api/monitor/add_managed_directory.py` - `add_managed_directory()` function
  - `wks/api/monitor/remove_managed_directory.py` - `remove_managed_directory()` function
  - `wks/api/monitor/set_managed_priority.py` - `set_managed_priority()` function
  - `wks/api/monitor/config.py` - `MonitorConfig` Pydantic model
  - `wks/api/monitor/models.py` - Status/Validation result models
  - `wks/api/monitor/helpers.py` - Helper functions (canonicalize_path, etc.)
  - `wks/api/monitor/app.py` - Typer app that imports and registers all functions
- **No Classes**: Functions instead of static method classes (classes were just namespaces)
- **Auto-Generated CLI**: Typer automatically creates CLI from function signatures
- **Auto-Generated MCP Schema**: Adapter introspects Typer commands to generate MCP JSON schemas
- **Config Injection**: Wrapper/decorator loads config and injects it into functions
- **Entry Points**: `wks/cli.py` (CLI) and `wks/mcp.py` (MCP server) - both call `wks/api/monitor/` functions

## Implementation Plan

### Phase 1: Infrastructure Setup

1. **Add dependencies** (`pyproject.toml`)
   - Add `typer` and `pydantic` to `project.dependencies` list
   - Verify installation works

2. **Create `wks/api/` module structure**
   - `wks/api/__init__.py` - Module initialization
   - `wks/api/base.py` - Base utilities (config injection decorator, MCP adapter utilities)
   - `wks/api/monitor/` - Directory for monitor API functions (one file per function)

3. **Helper functions organization**
   - **Monitor-specific helpers**: `wks/api/monitor/_*.py` (prefixed with `_` to indicate non-public)
     - One file per helper function (e.g., `_build_canonical_map.py`, `_validate_path_conflicts.py`)
   - **Cross-domain utilities**: `wks/utils/` (flat structure, no subdirectories)
     - One file per utility function (e.g., `canonicalize_path.py`)
     - Functions used by multiple domains (monitor, vault, transform, etc.)

4. **Create config injection decorator** (`wks/api/base.py`)
   - Decorator that loads config and injects it as first parameter
   - Handles both dict config (from load_config) and WKSConfig dataclass
   - Can be applied to Typer command functions

5. **Create MCP adapter utilities** (`wks/api/base.py`)
   - Function to introspect Typer command and generate MCP JSON schema
   - Uses Pydantic's `TypeAdapter.json_schema()` for type conversion
   - Handles enum types, optional parameters, defaults
   - Extracts descriptions from Pydantic `Field(..., description="...")` and function docstrings
   - Maps to MCP's inputSchema format correctly

### Phase 2: Migrate Monitor Tools to Function-Based Architecture

6. **Move shared utilities to `wks/utils/`**
   - Move `canonicalize_path()` from `wks/monitor/operations.py` to `wks/utils/canonicalize_path.py`
   - This is a general path normalization utility used across domains

7. **Create `wks/api/monitor/` directory structure (one file per function)**
   - Move monitor-specific helper functions to `wks/api/monitor/_*.py` (prefixed with `_` for non-public)
   - Move `_build_canonical_map()` from `wks/monitor/controller.py` to `wks/api/monitor/_build_canonical_map.py`
   - Move validation helper functions to `wks/api/monitor/_*.py` files
   - One file per helper function (filename matches function name, prefixed with `_`)

8. **Create public API functions in `wks/api/monitor/`**
   - `__init__.py` - Export all functions
   - `config.py` - Move `MonitorConfig` from `wks/monitor/config.py`
   - `models.py` - Move status/validation models from `wks/monitor/status.py`
   - Create `wks/utils/monitor/` directory for shared helper functions
     - Move `canonicalize_path()` from `wks/monitor/operations.py` to `wks/utils/monitor/canonicalize_path.py`
     - Move `_build_canonical_map()` from `wks/monitor/controller.py` to `wks/utils/monitor/build_canonical_map.py`
     - Move validation helpers to individual files in `wks/utils/monitor/`
   - `get_status.py` - Convert `MonitorController.get_status()` to `get_status()` function
   - `check_path.py` - Convert `MonitorController.check_path()` to `check_path()` function
   - `validate_config.py` - Convert `MonitorController.validate_config()` to `validate_config()` function
   - `get_list.py` - Convert `MonitorController.get_list()` to `get_list()` function
   - `add_to_list.py` - Convert `MonitorOperations.add_to_list()` to `add_to_list()` function
   - `remove_from_list.py` - Convert `MonitorOperations.remove_from_list()` to `remove_from_list()` function
   - `get_managed_directories.py` - Convert `MonitorController.get_managed_directories()` to function
   - `add_managed_directory.py` - Convert `MonitorOperations.add_managed_directory()` to function
   - `remove_managed_directory.py` - Convert `MonitorOperations.remove_managed_directory()` to function
   - `set_managed_priority.py` - Convert `MonitorOperations.set_managed_priority()` to function
   - `app.py` - Create Typer app, import all functions, and register all commands

7. **Convert classes to functions (one function per file)**
   - Replace `MonitorController.get_status()` → `wks.api.monitor.get_status.get_status()`
   - Replace `MonitorController.check_path()` → `wks.api.monitor.check_path.check_path()`
   - Replace `MonitorController.validate_config()` → `wks.api.monitor.validate_config.validate_config()`
   - Replace `MonitorOperations.add_to_list()` → `wks.api.monitor.add_to_list.add_to_list()`
   - Replace all static methods with plain functions, one per file
   - Import shared utilities from `wks.utils` (e.g., `from wks.utils.canonicalize_path import canonicalize_path`)
   - Import monitor-specific helpers from `wks.api.monitor._*` modules
   - Each function file imports only what it needs

9. **Create Typer app** (`wks/api/monitor/app.py`)
   - `monitor_app = typer.Typer()` for monitor subcommands
   - Register all monitor commands using `@monitor_app.command()` decorators
   - Apply `@inject_config` decorator to all commands
   - Functions handle display directly using `get_display("cli")` when called from CLI

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
    - Import `monitor_app` from `wks.api.monitor.app`
    - Add as subcommand: `app.add_typer(monitor_app, name="monitor")`
    - **No wrapper functions needed** - Typer handles everything
    - Display is handled inside Typer functions using `get_display("cli")`

14. **Remove old monitor CLI code** (`wks/cli/__init__.py`)
    - Remove `_cmd_monitor_*` wrapper functions (no longer needed)
    - Remove `_call()` usage for monitor commands (CLI calls Typer functions directly)

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

### Phase 6: Cleanup & Simplification

17. **Remove obsolete code**
    - Remove `_define_monitor_*_tools()` static methods from `MCPServer`
    - Remove old `_tool_monitor_*` handler methods (if not used elsewhere)
    - **Remove `wks/monitor/` directory entirely** - all functionality moved to `wks/api/monitor/`
    - Clean up any unused imports

18. **Simplify architecture - CLI calls API directly**
    - **Architecture**: CLI → API (Typer functions) → Controller
    - **Implementation**:
      - Import `monitor_app` from `wks.api.monitor` directly and add as subcommand (no wrapper functions)
      - Remove CLI wrapper functions (`monitor_status_command`, etc.) - they're unnecessary
      - Typer functions return raw data (dict), not MCPResult
      - Typer functions handle display directly using `get_display("cli")` when called from CLI
      - MCP layer wraps in MCPResult only when needed (for external MCP clients)
      - Remove `@display_output` decorator (does nothing, just passes through)
    - **Result**: Simpler call stack - `CLI → Typer function → Controller` (no MCP bridge for CLI)
    - **Rationale**: MCP is for external clients (Cursor, Claude Desktop), not for our own CLI. CLI should use the API directly.

## Key Files to Modify

- `pyproject.toml` - Add typer and pydantic dependencies
- `wks/api/base.py` (new) - Infrastructure (config decorator, MCP adapter)
- `wks/api/monitor/_*.py` - Monitor-specific non-public helper functions (prefixed with `_`)
- `wks/utils/canonicalize_path.py` (new) - Shared path canonicalization utility
- `wks/api/monitor/` (new directory) - All monitor functionality as functions (one file per function)
  - `__init__.py` - Export all functions
  - `get_status.py` - `get_status()` function
  - `check_path.py` - `check_path()` function
  - `validate_config.py` - `validate_config()` function
  - `get_list.py` - `get_list()` function
  - `add_to_list.py` - `add_to_list()` function
  - `remove_from_list.py` - `remove_from_list()` function
  - `get_managed_directories.py` - `get_managed_directories()` function
  - `add_managed_directory.py` - `add_managed_directory()` function
  - `remove_managed_directory.py` - `remove_managed_directory()` function
  - `set_managed_priority.py` - `set_managed_priority()` function
  - `config.py` - `MonitorConfig` Pydantic model
  - `models.py` - Status/Validation result models
  - `app.py` - Typer app that imports and registers all functions
- **Shared Utilities**: `wks/utils/monitor/` for non-public helper functions used by multiple monitor functions
  - One file per helper function (e.g., `canonicalize_path.py`, `build_canonical_map.py`)
  - Functions like `canonicalize_path()`, `build_canonical_map()`, `validate_path_conflicts()`, etc.
- **Shared Utilities**: `wks/utils/monitor/` for non-public helper functions used by multiple monitor functions
  - `canonicalize_path.py` - `canonicalize_path()` helper function
  - `build_canonical_map.py` - `build_canonical_map()` helper function
  - `validate_path_conflicts.py` - `validate_path_conflicts()` helper function
  - `validate_path_redundancy.py` - `validate_path_redundancy()` helper function
  - `validate_dirnames.py` - `validate_dirnames()` helper function
  - `validate_globs.py` - `validate_globs()` helper function
  - Other shared validation/helper functions
- `wks/mcp_server.py` - Update to use Typer tools from `wks/api/monitor/`
- `wks/cli/__init__.py` - Import and use `monitor_app` from `wks/api/monitor/app.py`
- `tests/test_mcp_server.py` - Update tests
- `tests/test_cli_*.py` - Update CLI tests
- **Remove**: `wks/monitor/` directory (migrated to `wks/api/monitor/`)

## Key Design Decisions

1. **No Classes**: Replace `MonitorController`, `MonitorOperations`, `MonitorValidator` classes (which are just namespaces) with plain functions
2. **One File Per Function Rule**: File name exactly matches function name (e.g., `get_status()` in `get_status.py`, `check_path()` in `check_path.py`)
3. **Config Injection**: Use decorator pattern to inject config, keeping function signatures clean
4. **Direct CLI Access**: CLI calls Typer functions directly (no MCP bridge) - `CLI → Typer function → Controller logic`
5. **MCP Wraps API**: MCP server wraps Typer functions in MCPResult for external clients
6. **Incremental Migration**: Only monitor tools migrate; other tools remain unchanged
7. **Backward Compatibility**: MCP tool names and CLI command names remain the same
8. **Type Safety**: Use Pydantic models for validation and schema generation
9. **Return Raw Data**: Functions return dict/data directly; MCP layer wraps in MCPResult when needed
10. **Display in Functions**: Typer functions handle display directly using `get_display("cli")` when called from CLI
11. **Schema Descriptions**: Use Pydantic `Field(..., description="...")` for MCP inputSchema descriptions

## Technical Considerations

### CLI Integration Strategy
- **Solution**: Import Typer app directly and add as subcommand - no bridge needed
  - `from wks.api.monitor.app import monitor_app`
  - `app.add_typer(monitor_app, name="monitor")`
  - Typer handles all argument parsing automatically

### Return Value vs Print Duality
- **Problem**: Typer commands typically print() and return None, but MCP needs structured return values
- **Solution**:
  - Functions return raw data (dict) directly
  - When called from CLI, functions handle display using `get_display("cli")` and call `display.json_output()`
  - When called from MCP, functions return data and MCP layer wraps in MCPResult
  - No decorator needed - display logic is inside the function

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
- CLI calls Typer functions directly (no MCP bridge)
- Functions handle display internally when called from CLI
- `wks/monitor/` directory removed (functionality in `wks/api/monitor/`)

## Implementation Todos

1. Add typer and pydantic to pyproject.toml dependencies
2. Create wks/api/ module structure with __init__.py, base.py
3. Create config injection decorator in wks/api/base.py
4. Create MCP adapter utilities to introspect Typer commands and generate JSON schemas
5. Create wks/api/monitor/ directory structure (one file per function)
6. Move MonitorConfig from wks/monitor/config.py to wks/api/monitor/config.py
7. Move status/validation models from wks/monitor/status.py to wks/api/monitor/models.py
8. Create wks/utils/monitor/ directory for shared helper functions
9. Move helper functions from wks/monitor/ to wks/utils/monitor/ (one file per function)
9. Create wks/api/monitor/get_status.py with get_status() function (from MonitorController.get_status)
10. Create wks/api/monitor/check_path.py with check_path() function (from MonitorController.check_path)
11. Create wks/api/monitor/validate_config.py with validate_config() function (from MonitorController.validate_config)
12. Create wks/api/monitor/get_list.py with get_list() function (from MonitorController.get_list)
13. Create wks/api/monitor/add_to_list.py with add_to_list() function (from MonitorOperations.add_to_list)
14. Create wks/api/monitor/remove_from_list.py with remove_from_list() function (from MonitorOperations.remove_from_list)
15. Create wks/api/monitor/get_managed_directories.py with get_managed_directories() function
16. Create wks/api/monitor/add_managed_directory.py with add_managed_directory() function
17. Create wks/api/monitor/remove_managed_directory.py with remove_managed_directory() function
18. Create wks/api/monitor/set_managed_priority.py with set_managed_priority() function
19. Create wks/api/monitor/app.py - Typer app that imports all functions and registers commands
20. Update MCPServer._define_monitor_tools() to use Typer introspection instead of manual schemas
21. Update MCPServer._build_tool_registry() to route monitor tools to Typer functions
22. Integrate monitor Typer app into CLI (import from wks.api.monitor.app)
23. Remove old _cmd_monitor_* functions from wks/cli/__init__.py
24. Update tests for monitor tools to work with new function-based implementation
25. Remove obsolete _define_monitor_*_tools() methods and old _tool_monitor_* handlers from MCPServer
26. Remove wks/monitor/ directory entirely (all functionality moved to wks/api/monitor/)
