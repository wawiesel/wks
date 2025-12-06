# WKS Python Package

Developer entry point for the core layers used by MCP and CLI. Business logic lives in controllers under each subpackage; keep the CLI and MCP thin. See docs/specifications/wks.md for scope (index/search/patterns are future work).

## Directory Structure

The `wks` package contains exactly 4 top-level directories:

- **`api/`** - Domain-specific API modules (config, db, monitor, etc.) following the 4-stage pattern
- **`cli/`** - CLI routing layer that delegates to domain apps
- **`mcp/`** - MCP (Model Context Protocol) server implementation
- **`utils/`** - Basic utility functions following single file == function/class rule, used by multiple API domains

The code is in a state of flux right now. A rewrite is focusing on using the
pydantic and typer to provide a clear pathway from the core business logic in the API. The monitor and database (db) layers at api/monitor and api/db are currently good.
