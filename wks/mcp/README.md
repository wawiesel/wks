# MCP Layer

The MCP layer provides a JSON-RPC interface for WKS command contracts. MCP stays thin by discovering and calling `wks/api/*/cmd*.py` functions, which in turn delegate into the shared `wks/services/` layer.

## Architecture

```text
MCP client
  -> wks/mcp/server.py
  -> wks/api/*/cmd*.py
  -> wks/services/*
```

Key points:

- MCP and CLI share the same command wrappers.
- Shared business logic lives below those wrappers in `wks/services/`.
- Tool schemas are generated from command signatures plus MCP-specific overrides.
- MCP owns protocol handling, not business logic.

## Discovery

The MCP server automatically:

1. Scans `wks/api/` for command modules.
2. Discovers `cmd_*.py`, `cmd.py`, and root `cmd_*.py` functions.
3. Builds object-shaped input schemas from command signatures.
4. Creates tool handlers that call the command functions.

Normal command additions do not require MCP-specific wiring changes.

## Tool Naming

Tool names follow the command domain:

- `search`
- `cat`
- `monitor_status`
- `config_show`

## Transport Boundary

MCP converts `StageResult` command output into structured JSON packets for tool callers. It does not contain domain logic or duplicate validation already owned by the shared service/core and command layers.

## SSE Proxy

The stdio MCP server can also be fronted by the SSE proxy in `wks/mcp/sse_proxy.py` for clients that need HTTP transport.
