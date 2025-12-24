# MCP Installation API

This directory implements the MCP Installation Management API. It manages WKS MCP server registrations in various agent configuration files.

## Core Principles

**One file = one thing**: Every exported function lives in its own file.

**Typing**: Uses `McpConfig` and `McpInstallation` discriminated unions for validation.

## Files
- `cmd_list.py` — List known MCP installations and their status
- `cmd_install.py` — Install WKS into an MCP client configuration
- `cmd_uninstall.py` — Uninstall WKS from an MCP client configuration
- `McpConfig.py` — Configuration models
- `McpServersJsonInstall.py` — Logic for `mcpServers.json` type installations

## Usage
Commands are exposed via CLI (`wksc mcp`) and MCP (`wksm_mcp_*`).
