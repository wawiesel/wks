# Configuration Specification

**Config Location**: `~/.wks/config.json` (default)

The config directory can be customized via the `WKS_HOME` environment variable:
```bash
export WKS_HOME="/custom/path"  # Config at /custom/path/config.json
```

**Viewing Configuration**:
```bash
wksc config    # Print effective config (table in CLI, JSON in MCP)
```

**Top-Level Structure**:

```json
{
  "monitor": { /* Filesystem tracking configuration */ },
  "vault": { /* Knowledge graph configuration */ },
  "db": { /* MongoDB connection settings */ },
  "transform": { /* Document conversion engines */ },
  "diff": { /* Comparison engines */ },
  "index": { /* Search indices */ },
  "search": { /* Search behavior */ },
  "display": { /* UI formatting */ }
}
```
