# Configuration Specification

**Note**: This specification needs to be updated to align with the principles established in the monitor and database specifications. It should follow the config-first approach (configuration discussed early, database schema discussed later), remove implementation details, and focus on WHAT (interface, behavior, requirements) rather than HOW (implementation details).


**Config Location**: `~/.wks/config.json`

The config directory can be customized via the `WKS_HOME` environment variable:
```bash
export WKS_HOME="/custom/path"  # Config at /custom/path/config.json
```

**Viewing Configuration**:
```bash
wksc config              # List all configuration section names
wksc config <section>    # Show configuration for a specific section (e.g., 'monitor', 'db', 'vault')
```

**Output Format**:
- **CLI**: Auto-formatted table for section names, JSON for section data
- **MCP**: JSON format for both section names and section data

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
