# Configuration Specification

**Config Location**: `~/.wks/config.json`

The config directory can be customized via the `WKS_HOME` environment variable:
```bash
export WKS_HOME="/custom/path"  # Config at /custom/path/config.json
```

**Viewing Configuration**:
```bash
wksc config    # Print effective config (table in CLI, JSON in MCP)
```

## Configuration Requirements

**All configuration values must be present in the config file.** There are no defaults in code. If a required field is missing from `~/.wks/config.json`, validation will fail immediately with a clear error message.

**Defaults in code are an error.** Configuration classes must use `Field(...)` (required) for all fields - never `Field(default=...)` or `Field(default_factory=...)`. If a value should be optional, it must be explicitly marked as `Optional[...]` in the type annotation, but the config file must still provide a value (which may be `null`).

**Top-Level Structure**:

```json
{
  "monitor": { /* Filesystem tracking configuration */ },
  "vault": { /* Knowledge graph configuration */ },
  "db": { /* Database connection settings */ },
  "transform": { /* Document conversion engines */ },
  "diff": { /* Comparison engines */ },
  "index": { /* Search indices */ },
  "search": { /* Search behavior */ },
  "display": { /* UI formatting */ }
}
```
