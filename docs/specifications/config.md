# Configuration Specification

The WKS configuration system provides a unified interface for viewing and managing all WKS configuration sections. Configuration is stored in a single JSON file and can be viewed via CLI or MCP interfaces.

**CLI Interface**:
```bash
wksc config              # List all configuration section names
wksc config <section>    # Show configuration for a specific section (e.g., 'monitor', 'database', 'vault')
```

**MCP Interface**:
- `wksm_config` - Returns complete configuration as JSON

**Config Location**: `{WKS_HOME}/config.json`

The config directory can be customized via the `WKS_HOME` environment variable (defaults to `~/.wks` if not set):
```bash
export WKS_HOME="/custom/path"  # Config at /custom/path/config.json
```

**Output Format**:
- **CLI**: Output format is controlled by the global `--display` option (default: `yaml`). Available formats:
  - `--display yaml` (default): YAML-formatted output
  - `--display json`: JSON-formatted output
- **MCP**: Always returns JSON format (equivalent to `--display json`)

## Configuration Requirements

**All configuration sections and fields must be present in the config file.** If a required field is missing from `{WKS_HOME}/config.json`, validation will fail immediately with a clear error message.

**No optional fields**: All sections listed in the top-level structure must be present in the config file. Every section must have a value.

**Top-Level Structure**:

The configuration file contains the following sections. Each section is described in its respective specification document:

- `monitor` - Filesystem tracking configuration (see `docs/specifications/monitor.md`)
- `vault` - Knowledge graph configuration (see `docs/specifications/vault.md`)
- `database` - Database connection settings (see `docs/specifications/database.md`)
- `transform` - Document conversion engines (see `docs/specifications/transform.md`)
- `diff` - Comparison engines (see `docs/specifications/diff.md`)
- `index` - Search indices (see `docs/specifications/index.md`)
- `search` - Search behavior (see `docs/specifications/search.md`)
- `display` - UI formatting (see `docs/specifications/display.md`)
- `daemon` - Daemon service configuration (see `docs/specifications/daemon.md`)
- `mcp` - MCP server installation locations (see `docs/specifications/mcp.md`)
