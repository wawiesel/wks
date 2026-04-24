# WKS Python Package

Developer entry point for WKS shared services, command wrappers, and thin transports.

## Directory Structure

The main execution layers under `wks/` are:

- `services/` - shared typed service/core logic and the `WKSService` Python facade
- `api/` - domain-specific command wrappers returning `StageResult`
- `cli/` - CLI routing layer that delegates to command wrappers
- `mcp/` - MCP server implementation that delegates to command wrappers
- `rest/` - read-only REST transport over the shared service layer

## Architecture

WKS follows a service-under-command design:

- shared logic lives in `wks/services/`
- command contracts live in `wks/api/*/cmd*.py`
- CLI and MCP stay thin by calling command wrappers
- REST stays thin by calling the shared services directly

### Layer Responsibilities

**Service Layer (`wks/services/`)**
- Contains typed request/response models and shared business logic
- No `StageResult`, no transport formatting, no protocol envelopes
- Example: `wks/services/search.py`

**Command Layer (`wks/api/`)**
- Wraps shared services into `StageResult`
- Preserves one-command-per-file traceability
- Example: `wks/api/search/cmd.py`

**CLI Layer (`wks/cli/`)**
- Thin Typer apps that wrap command functions
- Handles argument parsing and display formatting

**MCP Layer (`wks/mcp/`)**
- JSON-RPC server that exposes command functions as tools
- Generates tool schemas from command signatures

**REST Layer (`wks/rest/`)**
- Read-only FastAPI app over shared service functions
- Maps typed service failures to HTTP status codes

### Example Flow

```text
CLI: wksc search reactor
  -> wks/api/search/cmd.py
  -> wks/services/search.py

MCP: search({"query": "reactor"})
  -> wks/api/search/cmd.py
  -> wks/services/search.py

REST: GET /search?query=reactor
  -> wks/rest/server.py
  -> wks/services/search.py
```
