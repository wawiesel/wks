# Agent 2: List Management Tools

**Branch:** `agent2-list-tools`
**Status:** ASSIGNED

## Objective

Implement the list management monitor tools (list, add, remove) with full MCP integration, following the pattern established by Agent 1.

## Scope

**In Scope:**
- Create Pydantic `MonitorListName` enum
- Implement list management tools: `monitor_list`, `monitor_add`, `monitor_remove`
- Integrate these tools into MCP server
- Update MCP server to use Typer introspection for these 3 tools

**Out of Scope:**
- Basic tools (Agent 1)
- Managed directory tools (Agent 3)
- CLI integration (can be done after all tools are integrated)

## Tasks

### 1. Create Pydantic Models
- [ ] Create `MonitorListName` enum in `wks/api/monitor.py` with values:
  - `include_paths`, `exclude_paths`
  - `include_dirnames`, `exclude_dirnames`
  - `include_globs`, `exclude_globs`
- [ ] Use `Field(..., description="...")` for all enum values

### 2. Implement List Management Tools
- [ ] `monitor_list(config, list_name: MonitorListName)` - Get list contents
- [ ] `monitor_add(config, list_name: MonitorListName, value: str)` - Add value to list
- [ ] `monitor_remove(config, list_name: MonitorListName, value: str)` - Remove value from list

**Requirements:**
- Use `@monitor_app.command()` decorator (monitor_app created by Agent 1)
- Apply `@inject_config` decorator
- Return MCPResult/dict (no printing)
- Copy logic from `_tool_monitor_list`, `_tool_monitor_add`, `_tool_monitor_remove` in `wks/mcp_server.py`
- Handle config file reading/writing (see existing handlers)

### 3. MCP Server Integration
- [ ] Update `_define_monitor_list_tools()` to use Typer introspection for the 3 list tools
- [ ] Update `_build_tool_registry()` to route `wksm_monitor_list`, `wksm_monitor_add`, `wksm_monitor_remove` to Typer functions
- [ ] Ensure `_handle_call_tool()` works with these tools

## Success Criteria

- [ ] All 3 list management tools work via MCP
- [ ] MCP schemas are auto-generated from Typer commands
- [ ] No manual schema definitions for list tools
- [ ] Pydantic enum properly validates list_name parameter

## Dependencies

- Agent 1's infrastructure (base.py, monitor_app) must be merged first
- Agent 2 should pull latest from campaign branch before starting

## Notes

- Follow the exact pattern established by Agent 1
- Reuse `monitor_app` instance created by Agent 1
- Focus on the 3 list management tools only
