# Agent 1: Infrastructure & Basic Monitor Tools

**Branch:** `agent1-basic-tools`
**Status:** ASSIGNED

## Objective

Create the API module infrastructure and implement the basic monitor tools (status, check, validate) with full MCP integration. This agent establishes the foundation pattern that other agents will follow.

## Scope

**In Scope:**
- Add typer and pydantic dependencies
- Create `wks/api/` module structure
- Implement base utilities (config injection, display output, MCP adapter)
- Implement basic monitor tools: `monitor_status`, `monitor_check` (note: `status` includes validation and exits with error code if issues found)
- Integrate these tools into MCP server
- Update MCP server to use Typer introspection for these 3 tools

**Out of Scope:**
- List management tools (Agent 2)
- Managed directory tools (Agent 3)
- CLI integration (can be done after all tools are integrated)

## Tasks

### 1. Infrastructure Setup
- [ ] Add `typer` and `pydantic` to `pyproject.toml` dependencies
- [ ] Create `wks/api/__init__.py` with module docstring
- [ ] Create `wks/api/base.py` with:
  - `inject_config` decorator
  - `display_output` decorator
  - `get_typer_command_schema()` function for MCP schema generation
- [ ] Create `wks/api/monitor.py` skeleton

### 2. Implement Basic Monitor Tools
- [ ] `monitor_status(config)` - Get filesystem monitoring status
- [ ] `monitor_check(config, path: str)` - Check if path would be monitored
- [ ] Note: `monitor_status` includes validation (no separate validate command needed)

**Requirements:**
- Use `@app.command()` decorator from Typer
- Apply `@inject_config` decorator
- Return MCPResult/dict (no printing)
- Copy logic from `_tool_monitor_status`, `_tool_monitor_check` in `wks/mcp_server.py`

### 3. Create Typer App Instance
- [ ] Create `monitor_app = typer.Typer()` instance
- [ ] Register the 3 basic commands

### 4. MCP Server Integration
- [ ] Add `_get_typer_tools_schema()` method to `MCPServer` that introspects `wks.api.monitor.monitor_app`
- [ ] Update `_define_monitor_basic_tools()` to use Typer introspection for the 3 basic tools
- [ ] Update `_build_tool_registry()` to route `wksm_monitor_status`, `wksm_monitor_check` to Typer functions
- [ ] Ensure `_handle_call_tool()` works with Typer-based tools

## Success Criteria

- [ ] All 3 basic monitor tools work via MCP
- [ ] MCP schemas are auto-generated from Typer commands
- [ ] No manual schema definitions for basic tools
- [ ] Code follows CONTRIBUTING.md guidelines

## Dependencies

- None (this establishes the pattern)

## Notes

- This agent creates the foundation that Agents 2 and 3 will follow
- Focus on getting the pattern right - other agents will replicate it
- MCP integration should be complete for these 3 tools
