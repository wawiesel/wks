# Infrastructure Specification

## Database

All layers store data in a configurable database backend. See [Database Specification](database.md) for details on database abstraction and supported backends.

Database operations:

```bash
# Query databases (simple pass-through to MongoDB)
wksc db query monitor              # Query filesystem state
wksc db query vault                # Query knowledge graph links
wksc db query transform            # Query transform cache metadata
wksc db query wks.monitor         # Query using full database.collection key
wksc db query monitor --query '{"priority": {"$gt": 10}}'  # Query with filter

# Reset databases (destructive)
wksc db reset monitor        # Clear filesystem state
wksc db reset vault          # Clear link graph
wksc db reset transform      # Clear transform cache and DB
```

## Service

**MCP Interface**:
- `wksm_service(action)` — Manage service (start, stop, restart, status, install, uninstall)

**CLI Interface**:
```bash
wksc service install         # Install launchd service (macOS)
wksc service uninstall       # Remove service
wksc service start           # Start daemon
wksc service stop            # Stop daemon
wksc service restart         # Restart daemon
wksc service status          # Show status and metrics (supports --live for auto-updating display)
```

## MCP Server

WKS exposes layers as MCP tools for AI assistant integration. Following SPEC principles: zero code duplication with business logic in controllers, view-agnostic structured data, and both CLI and MCP using the same controller methods.

**Installation**:
```bash
wksc mcp install              # Install to all supported clients
wksc mcp install --client cursor --client claude
```

**Running**:
```bash
wksc mcp run                  # Proxies to background daemon broker
wksc mcp run --direct         # Run inline for debugging
```
