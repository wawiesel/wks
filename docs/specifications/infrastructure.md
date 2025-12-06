# Infrastructure Specification

**Note**: This specification needs to be updated to align with the principles established in the monitor and database specifications. It should follow the config-first approach (configuration discussed early, database schema discussed later), remove implementation details, and focus on WHAT (interface, behavior, requirements) rather than HOW (implementation details).

## Database

All layers store data in a configurable database backend. See [Database Specification](database.md) for details on database abstraction and supported backends.

Database operations:

```bash
# List collections
wksc db list                           # List available collections

# Show collections (collection names are examples, not fixed)
wksc db show <collection>              # Show collection contents
wksc db show <collection> --query '{"key": "value"}'  # Show with filter
wksc db show <collection> --limit 100  # Limit number of results

# Reset collections (destructive)
wksc db reset <collection>        # Clear all documents from collection
```

**Collection Names**: Collection names are specified without the database prefix. The prefix from `db.prefix` configuration is automatically prepended. For example, with `prefix: "wks"`, specifying `monitor` accesses the `wks.monitor` collection. Users must never specify the prefix in collection names - only provide the collection name itself.

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
