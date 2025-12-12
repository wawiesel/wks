# WKS Utils

Basic utility functions and classes used across multiple parts of the API.

## Principles

- **Single file == function or class rule**: Each file exports exactly one function or class, and the filename matches the exported symbol name
- **No configuration dependencies**: Utils must not require any configuration information (no `WKSConfig` or domain-specific config)
- **Shared across domains**: Code should only be in `utils/` if it's used by multiple API domains (config, db, monitor, etc.)
- **Basic/primitive operations**: Utils contain low-level, reusable functionality

## Examples

Good candidates for `utils/`:
- Path manipulation helpers
- String formatting utilities
- Simple data transformation functions
- Common type validators
- Shared constants (if truly universal)

Not appropriate for `utils/`:
- Functions that require domain-specific configuration
- Business logic (should live in domain controllers)
- Code only used by a single domain (should live in that domain)
- CLI or MCP-specific code (should live in `cli/` or `mcp/`)
