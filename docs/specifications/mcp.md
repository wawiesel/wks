# MCP Server Specification

WKS exposes layers as MCP tools for AI assistant integration. Following SPEC principles: zero code duplication with business logic in controllers, view-agnostic structured data, and both CLI and MCP using the same controller methods.

**CLI Interface**:
```bash
wksc mcp list                                    # List available MCP server locations and installation status
wksc mcp install /path/to/settings.json          # Add WKS MCP server to specified settings file
wksc mcp uninstall /path/to/settings.json       # Remove WKS MCP server from specified settings file
```

**MCP Server Execution**:
The MCP server is run via a separate `wksm` command (not `wksc mcp run`). The `wksm` command is the entry point that MCP clients invoke to start the WKS MCP server.

**Configuration**:
MCP server installation locations are managed in `{WKS_HOME}/config.json` under the `mcp.installs` section. This section uses a `type/data` pattern similar to the database and daemon configurations:

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

**Installation Behavior**:
- `wksc mcp list` reads from `mcp.installs` configuration and checks each settings file to determine if WKS is already installed
- `wksc mcp install <path>` adds the WKS MCP server entry to the specified settings file, preserving all other entries
- `wksc mcp uninstall <path>` removes only the WKS MCP server entry from the specified settings file, leaving all other entries intact
- Each settings file is a JSON file containing an `mcpServers` object with server configurations

