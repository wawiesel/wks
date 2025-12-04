# Agent 3: Managed Directory Tools & CLI Integration

**Branch:** `agent3-managed-cli`
**Status:** ASSIGNED

## Objective

Implement the managed directory monitor tools with full MCP integration, then integrate all monitor tools into the CLI and clean up old code.

## Scope

**In Scope:**
- Implement managed directory tools: `monitor_managed_list`, `monitor_managed_add`, `monitor_managed_remove`, `monitor_managed_set_priority`
- Integrate these tools into MCP server
- Integrate all monitor tools into CLI with argparse bridge
- Remove old monitor CLI code
- Update tests
- Remove obsolete MCP server methods

**Out of Scope:**
- Basic tools (Agent 1)
- List management tools (Agent 2)

## Tasks

### 1. Implement Managed Directory Tools
- [ ] `monitor_managed_list(config)` - Get managed directories
- [ ] `monitor_managed_add(config, path: str, priority: int)` - Add managed directory
- [ ] `monitor_managed_remove(config, path: str)` - Remove managed directory
- [ ] `monitor_managed_set_priority(config, path: str, priority: int)` - Update priority

**Requirements:**
- Use `@monitor_app.command()` decorator (monitor_app created by Agent 1)
- Apply `@inject_config` decorator
- Return MCPResult/dict (no printing)
- Copy logic from `_tool_monitor_managed_*` handlers in `wks/mcp_server.py`

### 2. MCP Server Integration
- [ ] Update `_define_monitor_managed_tools()` to use Typer introspection for the 4 managed tools
- [ ] Update `_build_tool_registry()` to route all `wksm_monitor_managed_*` tools to Typer functions
- [ ] Ensure `_handle_call_tool()` works with these tools

### 3. CLI Integration
- [ ] Import `monitor_app` from `wks.api.monitor` in `wks/cli/__init__.py`
- [ ] Replace `_setup_monitor()` with argparse bridge using `nargs=argparse.REMAINDER`
- [ ] Create `_bridge_to_typer()` function that:
  - Extracts remaining args from argparse namespace
  - Invokes `monitor_app(args=args.rest, standalone_mode=False)`
  - Handles display argument integration
- [ ] Apply display output decorator at CLI entry point

### 4. Cleanup
- [ ] Remove old `_cmd_monitor_*` wrapper functions from `wks/cli/__init__.py`
- [ ] Remove old `_setup_monitor()` function
- [ ] Remove obsolete `_define_monitor_*_tools()` static methods from `MCPServer` (after confirming Typer versions work)
- [ ] Remove old `_tool_monitor_*` handler methods from `MCPServer` (after confirming Typer versions work)

### 5. Testing
- [ ] Update `test_mcp_server.py` to test Typer-based monitor tools
- [ ] Create or update `test_cli_monitor.py` using `typer.testing.CliRunner`
- [ ] Ensure all monitor tool tests pass

## Success Criteria

- [ ] All 4 managed directory tools work via MCP
- [ ] All monitor CLI commands work via Typer bridge
- [ ] Old code removed
- [ ] All tests pass
- [ ] No manual schema definitions remain for monitor tools

## Dependencies

- Agent 1's infrastructure must be merged
- Agent 2's list tools should be merged (for complete CLI integration)
- Agent 3 should pull latest from campaign branch before starting

## Notes

- This agent does the most integration work (CLI + cleanup)
- Can start on managed directory tools while waiting for Agent 2
- CLI integration should wait until all tools are in MCP
- Be careful with cleanup - ensure everything works before removing old code
