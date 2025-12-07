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
wksc config <section>    # Show configuration for a specific section (e.g., 'monitor', 'database', 'vault')
```

**Output Format**:
- **CLI**: Auto-formatted table for section names, JSON for section data
- **MCP**: JSON format for both section names and section data

## Configuration Requirements

**All configuration values must be present in the config file.** There are no defaults in code. If a required field is missing from `{WKS_HOME}/config.json`, validation will fail immediately with a clear error message.

**Defaults in code are an error.** Configuration classes must use `Field(...)` (required) for all fields - never `Field(default=...)` or `Field(default_factory=...)`. If a value should be optional, it must be explicitly marked as `Optional[...]` in the type annotation, but the config file must still provide a value (which may be `null`).

**Top-Level Structure**:

```json
{
  "monitor": { /* Filesystem tracking configuration */ },
  "vault": { /* Knowledge graph configuration */ },
  "database": { /* Database connection settings */ },
  "transform": { /* Document conversion engines */ },
  "diff": { /* Comparison engines */ },
  "index": { /* Search indices */ },
  "search": { /* Search behavior */ },
  "display": { /* UI formatting */ },
  "daemon": { /* Daemon service configuration */ },
  "mcp": { /* MCP server installation locations */ }
}
```

## Daemon Configuration

The `daemon` section configures how the WKS daemon runs as a system service. This configuration is used by `wksc daemon install` to create the appropriate service files. The configuration follows the same `type`/`data` pattern as the database configuration.

**Structure**:
```json
{
  "daemon": {
    "type": "macos",
    "data": {
      "label": "com.wieselquist.wks",
      "working_directory": "{WKS_HOME}",
      "log_file": "{WKS_HOME}/daemon.log",
      "error_log_file": "{WKS_HOME}/daemon.error.log",
      "keep_alive": true,
      "run_at_load": true
    }
  }
}
```

**Fields**:
- `type` (string, required): Platform/service manager type. Currently supported: `"macos"` (launchd). Additional types will be added in the future.
- `data` (object, required): Platform-specific configuration data. The structure depends on the `type` value.

**macOS (launchd) Data Fields**:
- `label` (string, required): Launchd service identifier, must follow reverse DNS naming (e.g., `com.wieselquist.wks`)
- `working_directory` (string, required): Directory where the daemon runs (paths starting with `~` are expanded to user home directory)
- `log_file` (string, required): Path to standard output log file (paths starting with `~` are expanded)
- `error_log_file` (string, required): Path to standard error log file (paths starting with `~` are expanded)
- `keep_alive` (boolean, required): Whether launchd should automatically restart the daemon if it exits
- `run_at_load` (boolean, required): Whether the service should start automatically when installed

## MCP Configuration

The `mcp` section configures where WKS MCP server installations are managed. This configuration is used by `wksc mcp list`, `wksc mcp install`, and `wksc mcp uninstall` commands.

**Structure**:
```json
{
  "mcp": {
    "installs": [
      {
        "type": "gemini",
        "data": {
          "settings_path": "~/Library/Application Support/Google/ai-studio/settings.json"
        }
      },
      {
        "type": "claude-desktop",
        "data": {
          "settings_path": "~/Library/Application Support/Claude/claude_desktop_config.json"
        }
      },
      {
        "type": "claude-code",
        "data": {
          "settings_path": "~/.config/claude-code/settings.json"
        }
      }
    ]
  }
}
```

**Fields**:
- `installs` (array, required): List of MCP client installation locations, each using the `type/data` pattern

**Install Entry Fields**:
- `type` (string, required): MCP client type identifier (e.g., `"gemini"`, `"claude-desktop"`, `"claude-code"`)
- `data` (object, required): Client-specific configuration data

**Client Data Fields**:
- `settings_path` (string, required): Path to the MCP client's settings file where the WKS server entry will be added/removed. Paths starting with `~` are expanded to the user home directory.

**Validation**:
- The `type` field must match a supported platform type
- All fields in `data` are required for the specified `type`
- Log file paths are expanded and must be writable by the daemon process
- The working directory must exist and be accessible
