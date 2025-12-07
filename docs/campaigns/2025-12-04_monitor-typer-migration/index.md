# WKS API Synchronization & Test Coverage Campaign

**Campaign Date:** 2025-12-04
**Status:** IN PROGRESS
**Branch:** `2025-12-04_monitor-typer-migration`

---

## Overview

Complete synchronization of all WKS API modules with their specifications and achievement of 100% unit test coverage. The goal is to ensure that `wks/api/config`, `wks/api/database`, `wks/api/monitor`, `wks/api/daemon`, and `wks/api/mcp` are fully implemented according to their specifications, with CLI and MCP interfaces both built on top of the same API layer.

**Architecture Principle**: CLI (`wksc`) and MCP (`wksm`) both sit on top of the API layer. Each `wksc <domain> <command>` has a corresponding `wksm_<domain>_<command>` MCP tool that uses the same underlying API function. The API functions are the single source of truth.

## Scope

### Target Modules

1. **`wks/api/config`**
   - CLI: `wksc config show`
   - MCP: `wksm_config`
   - Specification: `docs/specifications/config.md`
   - Goal: 100% unit test coverage, fully synchronized with spec

2. **`wks/api/database`**
   - CLI: `wksc database list/show/reset`
   - MCP: `wksm_database_*` tools
   - Specification: `docs/specifications/database.md`
   - Goal: 100% unit test coverage, fully synchronized with spec

3. **`wks/api/monitor`**
   - CLI: `wksc monitor status/check/sync/filter/priority`
   - MCP: `wksm_monitor_*` tools
   - Specification: `docs/specifications/monitor.md`
   - Goal: 100% unit test coverage, fully synchronized with spec

4. **`wks/api/daemon`**
   - CLI: `wksc daemon status/start/stop/restart/install/uninstall`
   - MCP: `wksm_daemon_*` tools
   - Specification: `docs/specifications/daemon.md`
   - Goal: 100% unit test coverage, fully synchronized with spec

5. **`wks/api/mcp`**
   - CLI: `wksc mcp list/install/uninstall`
   - MCP: `wksm_mcp_*` tools
   - Specification: `docs/specifications/mcp.md`
   - Goal: 100% unit test coverage, fully synchronized with spec
   - Note: The MCP server execution itself (`wksm` command) is separate infrastructure, but the MCP installation management commands belong in the API layer

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

### MCP Module Requirements

The `wks/api/mcp/` module must be created to handle MCP server installation management:

- **CLI Commands** (via `wks/api/mcp/app.py`):
  - `wksc mcp list` - List available MCP server locations and installation status
  - `wksc mcp install <path>` - Add WKS MCP server to specified settings file
  - `wksc mcp uninstall <path>` - Remove WKS MCP server from specified settings file

- **MCP Tools** (exposed via `wks/mcp/server.py`):
  - `wksm_mcp_list` - Equivalent to `wksc mcp list`
  - `wksm_mcp_install` - Equivalent to `wksc mcp install`
  - `wksm_mcp_uninstall` - Equivalent to `wksc mcp uninstall`

- **Configuration**: Uses `mcp.installs` section in `config.json` (see `docs/specifications/mcp.md`)

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
