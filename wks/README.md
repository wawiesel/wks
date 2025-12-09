# WKS Python Package

Developer entry point for the core layers used by MCP and CLI. Business logic lives in controllers under each subpackage; keep the CLI and MCP thin. See docs/specifications/wks.md for scope (index/search/patterns are future work).

## Directory Structure

The `wks` package contains exactly 4 top-level directories:

- **`api/`** - Domain-specific API modules (config, db, monitor, etc.) following the 4-stage pattern
- **`cli/`** - CLI routing layer that delegates to domain apps
- **`mcp/`** - MCP (Model Context Protocol) server implementation
- **`utils/`** - Basic utility functions following single file == function/class rule, used by multiple API domains

## Architecture: API-First Design

WKS follows a strict **API-First Design** principle where all business logic lives in the `api/` layer, and both CLI and MCP are thin wrappers that call the same API functions.

### Layer Responsibilities

**API Layer (`wks/api/`)**
- Contains **only business logic** - pure functions that return `StageResult` objects
- Zero CLI or MCP-specific code (no printing, no protocol handling)
- Functions are the single source of truth for execution
- Example: `wks/api/monitor/cmd_check.py` → `cmd_check(path: str) -> StageResult`

**CLI Layer (`wks/cli/`)**
- Thin Typer apps that wrap API functions
- Handles argument parsing, validation, and display formatting
- Calls API functions via `handle_stage_result()` wrapper
- Example: `wks/cli/monitor.py` → `check_command(ctx, path: str | None) -> None`

**MCP Layer (`wks/mcp/`)**
- JSON-RPC server that exposes API functions as MCP tools
- Uses Typer introspection for tool schemas (ensures CLI/MCP synchronization)
- Calls API functions directly for execution
- Example: `wksm_monitor_check` tool → calls `cmd_check()` directly

### Why MCP Uses Typer for Schemas

MCP attaches to the CLI layer (via Typer) for schema generation, not directly to the API. This ensures **CLI and MCP stay synchronized**:

1. **Single Source of Truth**: Typer command definitions are the authoritative schema for user-facing interfaces (CLI and MCP)
2. **Automatic Synchronization**: If CLI command changes, MCP automatically picks it up via Typer introspection
3. **Rich Metadata**: Typer provides help text, argument/option distinctions, and validation rules that API function signatures don't have
4. **Execution Still Direct**: MCP calls API functions directly for execution, ensuring business logic is shared

**Trade-off**: MCP has a dependency on CLI, but this is acceptable because:
- CLI must match API function signatures (or it breaks at runtime)
- Typer is the source of truth for user-facing interfaces
- The dependency ensures synchronization between CLI and MCP

### Example Flow

```
User: wksc monitor check /path/to/file
  ↓
CLI: check_command(ctx, path="/path/to/file")
  ↓
CLI: handle_stage_result(cmd_check)("/path/to/file")
  ↓
API: cmd_check(path="/path/to/file") -> StageResult
  ↓
CLI: Display StageResult via display layer

MCP: wksm_monitor_check({"path": "/path/to/file"})
  ↓
MCP: Schema from Typer introspection (check_command signature)
  ↓
MCP: Calls cmd_check(path="/path/to/file") directly
  ↓
MCP: Returns StageResult as JSON-RPC response
```

Both CLI and MCP call the same API function (`cmd_check`), ensuring identical behavior. MCP uses Typer for schemas to stay synchronized with CLI's user-facing interface.
