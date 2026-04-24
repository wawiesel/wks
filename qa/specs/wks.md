# WKS

WKS is a layered system for monitoring files, transforming content, tracking vault links, searching indexed material, and exposing those capabilities through shared transports.

## Required Surfaces

These interfaces are mandatory:

- Python service/core API in `wks/services/`
- CLI in `wksc`
- MCP in `wks/mcp/`
- Read-only REST in `wks/rest/`

Business logic is shared. Transports stay thin.

## Layering

```text
services/core
  -> cmd_* wrappers
    -> CLI
    -> MCP
  -> REST
```

Rules:

- Shared logic lives in services/core or lower-level reusable helpers.
- Command wrappers own command contracts, validation at the command boundary, and `StageResult`.
- CLI and MCP call command wrappers.
- REST calls typed services directly.
- No transport duplicates business logic.

## Configuration

- Configuration lives in `WKS_HOME/config.json`.
- Required values must be present in config and validated on load.
- No silent defaults, implicit substitutions, or compatibility shims.
- Database names follow `<prefix>.<collection>`.

## Output Contracts

- Command outputs are explicit Python models.
- The same command must return the same shape on success and failure.
- CLI writes user-facing progress/result text to STDERR and structured content to STDOUT.
- MCP returns structured JSON packets.
- REST maps typed service failures to explicit HTTP status codes.

## Global Requirements

- `wksc` supports `--display yaml|json`.
- CLI commands follow announce -> progress -> result -> output.
- CLI, MCP, and REST must stay behaviorally consistent for equivalent operations.
- All file URIs stored in the database include the hostname.
- URI creation is centralized; no ad hoc `file://...` formatting in domain code.

## Domain References

- [config.md](config.md)
- [database.md](database.md)
- [monitor.md](monitor.md)
- [vault.md](vault.md)
- [transform.md](transform.md)
- [diff.md](diff.md)
- [index.md](index.md)
- [search.md](search.md)
- [daemon.md](daemon.md)
- [service.md](service.md)
- [mcp.md](mcp.md)
