# Infrastructure Specification

## Database

All layers store data in MongoDB. The current CLI/MCP surface read-only queries; reset/maintenance commands are planned future work.

```bash
# Query databases
wksc db monitor              # Filesystem state
wksc db vault                # Knowledge graph links
wksc db transform            # Transform cache metadata
```

## Service

**MCP Interface**:
- `wksm_service()` — Get service status (other lifecycle actions are planned)

**CLI Interface**:
```bash
wksc service status          # Show status and metrics
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
