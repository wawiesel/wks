# MCP Installation Management Specification

The MCP module provides commands for managing WKS MCP server installations across various MCP client applications (agents).

**CLI Interface**:
```bash
wksc mcp list                                    # List installation names and their paths/status
wksc mcp install <name>                         # Install WKS MCP server for the named installation
wksc mcp uninstall <name>                       # Uninstall WKS MCP server for the named installation
```

**MCP Interface**:
- `wksm_mcp_list` - Equivalent to `wksc mcp list`
- `wksm_mcp_install` - Equivalent to `wksc mcp install`
- `wksm_mcp_uninstall` - Equivalent to `wksc mcp uninstall`

**Configuration**:
MCP server installation locations are managed in `{WKS_HOME}/config.json` under the `mcp.installs` section. Each installation has a unique name and uses a `type/data` pattern similar to the database and daemon configurations. Each installation also has an `active` boolean field that indicates whether WKS is currently installed:

```json
{
  "mcp": {
    "installs": {
      "gemini": {
        "type": "mcpServersJson",
        "active": true,
        "data": {
          "settings_path": "~/Library/Application Support/Google/ai-studio/settings.json"
        }
      },
      "claude-desktop-main": {
        "type": "mcpServersJson",
        "active": false,
        "data": {
          "settings_path": "~/Library/Application Support/Claude/claude_desktop_config.json"
        }
      },
      "claude-code-dev": {
        "type": "mcpServersJson",
        "active": true,
        "data": {
          "settings_path": "~/.config/claude-code/settings.json"
        }
      }
    }
  }
}
```

**Installation Types**:
- **`mcpServersJson`**: Generic type for any JSON file that follows the standard MCP servers pattern (contains an `mcpServers` object). This type can be used for any MCP client that stores server configurations in a JSON file with an `mcpServers` field. Currently, all supported agent types (gemini, claude-desktop, claude-code) use this standard pattern.
- **Future agent-specific types**: If an agent requires a non-standard installation mechanism, a new type can be added to support it.

**Installation Behavior**:
- `wksc mcp list` reads from `mcp.installs` configuration and displays each installation name along with its path and installation status (based on the `active` field)
- `wksc mcp install <name>` installs the WKS MCP server for the named installation, using whatever mechanism is appropriate for that agent type. If the installation entry already exists in the config, it sets `active: true`. If it doesn't exist, it creates a new entry with `active: true`.
- `wksc mcp uninstall <name>` removes the WKS MCP server installation for the named installation, using whatever mechanism is appropriate for that agent type. The installation entry remains in the config but `active` is set to `false`.
- The specific installation mechanism (file format, structure, location) depends on the agent type and may vary between different MCP clients
- Installation names are user-defined and can be any string that uniquely identifies a particular installation
- The `active` field tracks whether WKS is currently installed for that installation entry, allowing easy reinstallation by toggling the field

**Current Examples**:
The following are examples of currently supported agent types and their configuration:
- `gemini`: Uses a JSON settings file at `~/Library/Application Support/Google/ai-studio/settings.json`
- `claude-desktop`: Uses a JSON settings file at `~/Library/Application Support/Claude/claude_desktop_config.json`
- `claude-code`: Uses a JSON settings file at `~/.config/claude-code/settings.json`

Future agent types may use different file formats, locations, or installation mechanisms as required by their specific implementation.

