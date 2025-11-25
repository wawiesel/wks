# WKS (Wieselquist Knowledge System)

**Version:** 0.3.7
**Status:** Production-ready core features, similarity features under rework

AI-assisted file organization and knowledge management system with Obsidian vault integration.

## Features

- **Filesystem Monitoring**: Track and index files with priority-based weighting
- **Vault Link Management**: Bidirectional link tracking for Obsidian vaults
- **Transform Cache**: Document conversion (PDF → Markdown) with caching
- **Database Integration**: MongoDB for metadata and link storage
- **Service Daemon**: Background monitoring with automatic sync
- **MCP Server**: Model Context Protocol integration for AI assistants

## Install

### From Source

```bash
# Clone and setup
git clone <repo-url>
cd 2025-WKS

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e '.[all]'
```

### System Installation

```bash
# Install globally with pipx
pipx install .

# Or install in development mode
pipx install --force --editable .
```

## Quick Start

```bash
# Check version
wks0 --version

# View configuration
wks0 config

# Start monitoring service
wks0 service start

# Check service status
wks0 service status

# Sync vault links
wks0 vault sync

# View vault links
wks0 vault links ~/vault/Index.md

# Compare two files
wks0 diff myers file1.txt file2.txt

# Transform PDF to Markdown
wks0 transform docling document.pdf -o output.md
```

## MCP Server

WKS includes a Model Context Protocol (MCP) server for AI assistant integration.

### Installation

```bash
# Install MCP server configuration for all supported clients
wks0 mcp install

# Install for specific clients only
wks0 mcp install --client cursor --client claude
```

### Usage

The MCP server runs automatically when the WKS service is active:

```bash
wks0 service start    # Starts daemon with embedded MCP broker
wks0 mcp run          # Proxies to the running service
```

### Available Tools

**Filesystem Monitoring:**
- `wks_monitor_status` - Get monitoring status and configuration
- `wks_monitor_check` - Check if path would be monitored
- `wks_monitor_validate` - Validate configuration for conflicts
- `wks_monitor_list` - Get configuration list contents
- `wks_monitor_add/remove` - Modify configuration lists
- `wks_monitor_managed_*` - Manage directory priorities

**Vault Link Tracking:**
- `wks_vault_status` - Get vault link status summary
- `wks_vault_links` - Get all links to/from a specific file
- `wks_vault_sync` - Sync vault links to MongoDB

All tools return structured JSON and use the same business logic as CLI commands.

## Documentation

- **User Guide**: `SPEC.md` - System specification and usage
- **Contributing**: `CONTRIBUTING.md` - Development guidelines
- **Roadmap**: `ROADMAP.md` - Future development plans
- **Changelog**: `CHANGELOG.md` - Version history
- **AI Agent Guide**: `guides/CLAUDE.md` - Instructions for AI assistants

## Architecture

```
wks/
├── cli/              # Command-line interface
├── monitor/          # Filesystem monitoring
├── vault/            # Obsidian vault integration
├── transform/        # Document transformation
├── service/          # Background daemon
└── mcp/              # Model Context Protocol server
```

## Requirements

- Python 3.8+
- MongoDB 4.0+
- macOS/Linux (tested on macOS)

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_vault_indexer.py -v

# Check code quality
python -m mypy wks/
python -m pylint wks/
lizard wks/ -l python -C 15
```

## Current Status

**v0.3.7 (2025-01-24)**
- ✅ Core monitoring and vault features stable
- ✅ All 139 tests passing
- ✅ Code complexity reduced (CCN < 15 for all functions)
- ✅ MCP server fully functional and documented
- ✅ Diff and transform commands working
- 🚧 Similarity features disabled (under redesign)

## License

See LICENSE file for details.
