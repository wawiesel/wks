# MCP Layer

The MCP layer exposes WKS command contracts over JSON-RPC.

## Path

```text
MCP client
  -> wks/mcp/server.py
  -> wks/api/*/cmd*.py
  -> wks/services/*
```

## Rules

- MCP stays thin.
- Tool schemas are generated from command signatures plus MCP-specific overrides.
- MCP owns protocol handling, not business logic.
- Command wrappers remain the source of truth for command contracts.

## Naming

Examples:

- `search`
- `cat`
- `monitor_status`
- `config_show`

## SSE Proxy

`wks/mcp/sse_proxy.py` fronts the stdio server for clients that need HTTP transport.
