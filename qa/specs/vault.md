# Vault

The vault layer scans notes, rewrites supported file links, stores edges, and reports vault health.

## Rules

- Vault paths resolve relative to the configured base directory.
- Internal note URIs use the `vault:///...` scheme.
- Vault commands share one command contract across CLI and MCP.
