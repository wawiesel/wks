# WKS API Synchronization & Test Coverage Campaign

**Campaign Date:** 2025-12-04
**Status:** IN PROGRESS
**Branch:** `2025-12-04_monitor-typer-migration`
**Execution:** Single Agent Campaign

---

## Overview

Complete synchronization of all WKS API modules with their specifications and achievement of 100% unit test coverage. The goal is to ensure that `wks/api/config`, `wks/api/database`, `wks/api/monitor`, `wks/api/daemon`, and `wks/api/mcp` are fully implemented according to their specifications, with CLI and MCP interfaces both built on top of the same API layer.

This is a **single agent campaign** - one agent will work through all five API modules sequentially to achieve complete specification compliance and 100% test coverage.

**Architecture Principle**: CLI (`wksc`) and MCP (`wksm`) both sit on top of the API layer. Each `wksc <domain> <command>` has a corresponding `wksm_<domain>_<command>` MCP tool that uses the same underlying API function. The API functions are the single source of truth.

## Scope

### Target Modules

Implement each module according to its specification with 100% unit test coverage:

1. **`wks/api/config`** - See `docs/specifications/config.md`
2. **`wks/api/database`** - See `docs/specifications/database.md`
3. **`wks/api/monitor`** - See `docs/specifications/monitor.md`
4. **`wks/api/daemon`** - See `docs/specifications/daemon.md`
5. **`wks/api/mcp`** - See `docs/specifications/mcp.md`

**Note**: The MCP server execution itself (`wksm` command) is separate infrastructure, but the MCP installation management commands belong in the API layer.

## Requirements

### Implementation Requirements

1. **API-First Design**: All business logic lives in `wks/api/<domain>/` functions
2. **CLI Layer**: `wks/api/<domain>/app.py` registers Typer commands that call API functions
3. **MCP Layer**: `wks/mcp/server.py` defines MCP tools that call the same API functions
4. **Zero Duplication**: CLI and MCP share the exact same API functions - no separate implementations
5. **Specification Compliance**: All implementations must match their respective specification documents exactly

### Test Coverage Requirements

1. **100% Unit Test Coverage** for all public functions in:
   - `wks/api/config/`
   - `wks/api/database/`
   - `wks/api/monitor/`
   - `wks/api/daemon/`
   - `wks/api/mcp/` (when created)

2. **Test Organization**:
   - Unit tests in `tests/unit/test_wks_api_<domain>_*.py`
   - Integration tests in `tests/integration/test_<domain>*.py` (where appropriate)
   - All tests must be passing

3. **Test Quality**:
   - Tests must verify both success and error cases
   - Tests must verify specification compliance
   - Tests must verify CLI/MCP parity (same API function, different interfaces)


## Success Criteria

1. ✅ All five API modules (`config`, `database`, `monitor`, `daemon`, `mcp`) exist and are fully implemented
2. ✅ All implementations match their specifications exactly
3. ✅ 100% unit test coverage for all public API functions
4. ✅ All tests passing
5. ✅ CLI and MCP interfaces both use the same underlying API functions
6. ✅ No code duplication between CLI and MCP layers

## Out of Scope

- MCP server infrastructure (JSON-RPC handling, stdio transport) - remains in `wks/mcp/server.py`
- Other API modules (vault, transform, diff) - future campaigns
- Integration test coverage beyond what's necessary to verify API correctness
- **Vault <-> Daemon connection**: The daemon specification mentions maintaining vault links and syncing with Obsidian, but this functionality is not part of the current campaign. The daemon will focus only on filesystem monitoring and monitor database synchronization.

## Execution Notes

### Available Resources

- **Specifications**: All 5 target modules have complete specifications in `docs/specifications/`
- **Test Infrastructure**: pytest configured with 100% coverage threshold (`.coveragerc`), test organization documented (`tests/README.md`)
- **Code Patterns**: Examples in `wks/api/monitor/`, `wks/api/database/`, and `wks/api/daemon/` demonstrate the API-first pattern
- **MCP Integration**: Pattern for registering MCP tools visible in `wks/mcp/server.py` (see `_define_tools()`, `_build_tool_registry()`)
- **Key Reference Files**:
  - `wks/api/base.py` - `StageResult` pattern, `handle_stage_result()` decorator
  - `wks/api/monitor/README.md` - Detailed API pattern documentation
  - `wks/api/database/README.md` - Database API pattern documentation
  - `tests/unit/test_wks_api_monitor_*.py` - Example unit tests

### Known Issues

- **MCP Module**: `wks/api/mcp/` does not exist and must be created from scratch following the pattern established in other API modules.

### Implementation Order

Recommended sequence for single agent execution:
1. **config** - Simplest module, establishes baseline pattern
2. **database** - Core infrastructure, already well-structured
3. **monitor** - Complex but well-documented, good examples exist
4. **daemon** - Service management, backend pattern established
5. **mcp** - New module, create following established patterns

**MANDATORY REQUIREMENT - NO EXCEPTIONS**: Every single command in ALL of these modules MUST use the `progress_callback` pattern. EVERY command MUST have a progress bar, even if it completes in <1 second. This is non-negotiable. There are NO exceptions. Fast commands still show progress - they just complete quickly. The 4-stage execution pattern (Announce → Progress → Result → Output) is mandatory for every command. Do not attempt to skip progress for "fast" commands - this is a violation of the specification and will be rejected.

Each module should be completed (implementation + tests + verification) before moving to the next.

### Verification Steps

For each module, verify completion using these steps:

1. **Implementation Verification**:
   ```bash
   # Test CLI commands work
   wksc <domain> <command> [args]
   
   # Test MCP tools work (via MCP server)
   # Verify tool appears in wks/mcp/server.py _define_tools()
   ```

2. **Test Coverage Verification**:
   ```bash
   # Run coverage for specific module
   pytest tests/unit/test_wks_api_<domain>_*.py --cov=wks.api.<domain> --cov-report=term-missing
   
   # Verify 100% coverage (check output shows no missing lines)
   # Or run full coverage report:
   ./scripts/run_coverage.sh
   ```

3. **Specification Compliance**:
   - Compare CLI output with specification examples
   - Verify MCP tool schemas match specification
   - Check error messages match specification requirements

4. **Code Quality**:
   ```bash
   # Run quality checks
   ./scripts/check_quality.py
   
   # Ensure no lint errors
   ruff check wks/api/<domain>/
   ```

5. **Integration Test**:
   ```bash
   # Run integration tests if they exist
   pytest tests/integration/test_<domain>*.py -v
   ```

### Common Patterns to Follow

1. **API Function Structure**:
   - Function in `wks/api/<domain>/cmd_<name>.py`
   - Returns `StageResult` with `announce`, `result`, `output`, `success`
   - Loads config via `WKSConfig.load()` inside function
   - No CLI/MCP-specific code (pure business logic)

2. **CLI Integration**:
   - Register in `wks/api/<domain>/app.py` using Typer
   - Use `handle_stage_result()` decorator
   - Optional args use `typer.Argument(None, ...)` for auto-help

3. **MCP Integration**:
   - Add tool definition in `wks/mcp/server.py` `_define_<domain>_tools()`
   - Add handler in `_build_tool_registry()` that calls API function
   - Use `MCPResult` wrapper for MCP-specific formatting

4. **Test Structure**:
   - File: `tests/unit/test_wks_api_<domain>_cmd_<name>.py`
   - Test both success and error cases
   - Mock `WKSConfig.load()` for isolation
   - Verify `StageResult` structure matches expectations

### Module Completion Checklist

For each module, use this checklist before marking it complete:

- [ ] All API functions implemented in `wks/api/<domain>/cmd_*.py`
- [ ] All CLI commands registered in `wks/api/<domain>/app.py` and working
- [ ] All MCP tools registered in `wks/mcp/server.py` and working
- [ ] Unit tests exist for all public API functions (`tests/unit/test_wks_api_<domain>_*.py`)
- [ ] Test coverage shows 100% for the module (no missing lines)
- [ ] All tests passing (`pytest tests/unit/test_wks_api_<domain>_*.py -v`)
- [ ] CLI output matches specification examples
- [ ] MCP tool schemas match specification
- [ ] Error messages match specification requirements
- [ ] Code quality checks pass (`./scripts/check_quality.py`)
- [ ] No lint errors (`ruff check wks/api/<domain>/`)


### Coverage Verification Commands

```bash
# Verify coverage for a specific module
pytest tests/unit/test_wks_api_<domain>_*.py \
    --cov=wks.api.<domain> \
    --cov-report=term-missing \
    --cov-report=html

# Check coverage report shows 100%
# Look for "TOTAL" line - should show 100%
# HTML report: open htmlcov/index.html

# Full project coverage (to see overall status)
./scripts/run_coverage.sh

# Coverage should fail if below 100% (configured in .coveragerc)
```

### Common Pitfalls

1. **Forgetting MCP Integration**: After implementing CLI, remember to add MCP tool in `wks/mcp/server.py`
2. **Missing Error Cases**: Tests must cover both success AND failure paths
3. **Config Loading**: Always use `WKSConfig.load()` inside the function, not as a default parameter
4. **StageResult Structure**: Ensure all four fields (`announce`, `result`, `output`, `success`) are set correctly
5. **Import Paths**: Use `wks.api.<domain>` not `wks.<domain>` - the old paths don't exist anymore
6. **Coverage Exclusions**: Only use `# pragma: no cover` for truly unreachable code (like `if __name__ == "__main__"` blocks)

### CLI/MCP Parity Testing

To verify CLI and MCP use the same API function:

1. **Check the code**: Both should call the same function from `wks/api/<domain>/cmd_*.py`
2. **Test both interfaces**: Run the same operation via CLI and MCP, compare outputs
3. **Verify error handling**: Both should produce the same error messages for the same failures
4. **Check tool registry**: In `wks/mcp/server.py`, verify the MCP handler directly calls the API function

Example verification:
```python
# In wks/mcp/server.py, the handler should be:
"wksm_monitor_status": lambda config, args: MCPResult.from_stage_result(monitor_status())

# Not a separate implementation!
```

### Troubleshooting

- **Import Errors**: Ensure all imports use `wks.api.<domain>` paths (not `wks.<domain>`)
- **Coverage Gaps**: Check for `# pragma: no cover` comments - these are excluded intentionally. If coverage is below 100%, identify missing lines and add tests.
- **MCP Tool Not Appearing**: Verify tool is registered in both `_define_tools()` and `_build_tool_registry()` in `wks/mcp/server.py`
- **CLI Command Not Found**: Check `wks/cli/__init__.py` registers the domain app (e.g., `app.add_typer(config_app, name="config")`)
- **Tests Failing**: Ensure `WKSConfig.load()` is mocked in tests - don't rely on actual config file
- **StageResult Not Displaying**: Check that `handle_stage_result()` decorator is applied to CLI commands
