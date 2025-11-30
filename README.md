# WKS (Wieselquist Knowledge System)

AI-assisted file organization and knowledge management system with Obsidian vault integration.

## Overview

WKS provides intelligent filesystem monitoring, vault link tracking, and document transformation capabilities. Built as a layered architecture with MongoDB backend and Model Context Protocol (MCP) integration for AI assistants.

**Core Capabilities**:
- **Filesystem Monitoring**: Priority-based file tracking with automatic indexing
- **Vault Link Management**: Bidirectional link tracking for Obsidian vaults
- **Transform Layer**: Document conversion (PDF → Markdown) with intelligent caching
- **MCP Server**: AI assistant integration via Model Context Protocol
- **Service Daemon**: Background monitoring with automatic sync

## Install

### Requirements

- Python 3.10+
- MongoDB 4.0+
- macOS/Linux

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

# Optional: Install docling for PDF/Office transformation
pipx runpip wks0 install docling
```

# Initialize configuration
wks0 config

# Start background service
wks0 service start

# Check status
wks0 service status

# Sync vault links
wks0 vault sync

# View vault links
wks0 vault links ~/vault/Note.md
```

## MCP Integration

Install for AI assistants:
```bash
wks0 mcp install  # Install for all clients
wks0 mcp install --client cursor --client claude
```

Available tools: `wks_monitor_*`, `wks_vault_*` (see [SPEC.md](SPEC.md) for details)

## Architecture

See [SPEC.md](SPEC.md) for complete system specification.

**Key Layers**:
- **Monitor Layer**: Filesystem state tracking
- **Vault Layer**: Knowledge graph links
- **Transform Layer**: Document conversion
- **Diff Layer**: File comparison engines
- **Service Layer**: Background daemon

## Documentation

- **[SPEC.md](SPEC.md)**: Complete system specification
- **[NEXT.md](NEXT.md)**: Current development priorities
- **[CONTRIBUTING.md](CONTRIBUTING.md)**: Development guide, testing strategy

## Requirements

- Python 3.10+
- MongoDB 4.0+
- macOS/Linux

## License

See LICENSE file for details.
