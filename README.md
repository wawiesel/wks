# WKS

![Coverage](https://img.shields.io/badge/coverage-80.2%25-yellow)
![Mutation Score](https://img.shields.io/badge/mutation-70.0%25-red)
![Tests](https://img.shields.io/badge/tests-459_passing-brightgreen)
![Python](https://img.shields.io/badge/python-3.10+-blue)
![Status](https://img.shields.io/badge/status-alpha-orange)
![Docker Freshness](https://github.com/wawiesel/wks/actions/workflows/check-image-freshness.yml/badge.svg)

## Status
- Alpha: monitor, vault, transform, diff layers are under active development; CLI and MCP may change without notice.
- Upcoming priorities and ideas: [docs/campaigns/NEXT.md](docs/campaigns/NEXT.md).

## Code Quality Metrics

| Metric               |   Value |     Target | Status          |
|----------------------|--------:|-----------:|----------------:|
| **Code Coverage**    |   80.2% |       100% | ⚠️ Below Target |
| **Mutation Kill %**  |   70.0% |       ≥90% | ⚠️ Below Target |
| **Docker Freshness** |      v1 | Up to date | ✅ Pass          |

### Source Size Statistics

| Section   |   Files |    LOC |   Characters |   Tokens |   % Tokens |
|-----------|--------:|-------:|-------------:|---------:|-----------:|
| **api**   |     171 | 11,371 |      403,779 |   63,761 |      29.4% |
| **cli**   |      19 |  1,351 |       47,576 |    9,186 |       4.2% |
| **mcp**   |       9 |    509 |       17,883 |    3,396 |       1.6% |
| **utils** |      21 |    702 |       21,685 |    2,777 |       1.3% |
| **Total** |     220 | 13,933 |      490,923 |   79,120 |      36.5% |

### Testing Statistics

| Type                  |   Files |    LOC |   Characters |   Tokens |   % Tokens |
|-----------------------|--------:|-------:|-------------:|---------:|-----------:|
| **Unit Tests**        |      84 |  8,369 |      289,540 |   51,764 |      23.9% |
| **Integration Tests** |      12 |  1,449 |       49,136 |    8,884 |       4.1% |
| **Smoke Tests**       |       3 |    376 |       12,888 |    2,040 |       0.9% |
| **Total**             |      99 | 10,194 |      351,564 |   62,688 |      28.9% |

### Documentation Size Summary

| Category                    |   Files |   LOC |   Characters |   Tokens |   % Tokens |
|-----------------------------|--------:|------:|-------------:|---------:|-----------:|
| **User Documentation**      |       7 |   228 |        7,065 |    1,766 |       0.8% |
| **Developer Documentation** |      46 | 2,745 |      110,079 |   27,512 |      12.7% |
| **Specifications**          |      29 | 3,326 |      118,031 |   29,507 |      13.6% |
| **Total**                   |      82 | 6,299 |      235,175 |   58,785 |      27.1% |

### Infrastructure Summary

| Type             |   Files |   LOC |   Characters |   Tokens |   % Tokens |
|------------------|--------:|------:|-------------:|---------:|-----------:|
| **CI/CD**        |       4 |   375 |       11,022 |    2,755 |       1.3% |
| **Build/Config** |       5 |   167 |        3,906 |      975 |       0.4% |
| **Scripts**      |      15 | 1,927 |       65,757 |   12,663 |       5.8% |
| **Total**        |      24 | 2,469 |       80,685 |   16,393 |       7.6% |

**Mutation Testing**: Tests the quality of our test suite by introducing small changes (mutations) to the code and verifying that existing tests catch them. A score of 70.0% means 70.0% of introduced mutations were successfully killed by the test suite.

**Test Statistics**: 459 tests across 94 test files.

### Per-Domain Quality

| Domain    |   Coverage |   Mutation % |   Killed/Total |
|-----------|------------|--------------|----------------|
| cat       |        94% |          77% |          76/99 |
| config    |       100% |          69% |        183/264 |
| daemon    |        84% |          62% |        220/354 |
| database  |        91% |          71% |        447/631 |
| diff      |         0% |          N/A |            0/0 |
| link      |        98% |          70% |       831/1187 |
| log       |        94% |          66% |        359/547 |
| mcp       |        97% |          61% |        245/400 |
| monitor   |        99% |          69% |      1144/1666 |
| service   |        69% |          67% |          24/36 |
| transform |        87% |          80% |        620/779 |
| utils     |       100% |          N/A |            0/0 |
| vault     |       100% |          72% |       911/1270 |


## Overview

WKS provides intelligent filesystem monitoring, vault link tracking, and document transformation capabilities. Built as a layered architecture with MongoDB backend and Model Context Protocol (MCP) integration for AI assistants.

**Important Note**: WKS is currently in **alpha development status** and is **not yet ready for external users**. Our immediate focus is on comprehensive revision and ensuring 100% test coverage across existing features.

**Core Capabilities**:
- **Filesystem Monitoring**: Priority-based file tracking with automatic indexing
- **Vault Link Management**: Bidirectional link tracking for Obsidian vaults
- **Transform Layer**: Document conversion (PDF → Markdown) with intelligent caching
- **MCP Server**: AI assistant integration via Model Context Protocol
- **Service Daemon**: Background monitoring with automatic sync

## CLI Reference

| Command Group | Description |
|---------------|-------------|
| `wksc monitor` | Filesystem monitoring operations |
| `wksc vault` | Vault link management (Obsidian-style) |
| `wksc link` | Resource edge/link operations |
| `wksc daemon` | Daemon runtime management |
| `wksc service` | System service install/uninstall |
| `wksc config` | Configuration operations |
| `wksc database` | Database operations |
| `wksc mcp` | MCP server management |

<details>
<summary><strong>wksc monitor</strong> - Filesystem monitoring</summary>

- `status` - Get filesystem monitoring status
- `check <path>` - Check if path would be monitored and its priority
- `sync <path> [--recursive]` - Force update file/directory into database
- `filter show [list_name]` - Show filter list contents
- `filter add <list_name> <value>` - Add value to filter list
- `filter remove <list_name> <value>` - Remove value from filter list
- `priority show` - List all priority directories
- `priority add <path> <priority>` - Set priority for directory
- `priority remove <path>` - Remove priority directory

</details>

<details>
<summary><strong>wksc vault</strong> - Vault link management</summary>

- `status` - Get vault link health status
- `sync [path] [--recursive]` - Sync vault links to database
- `check [path]` - Check vault link health
- `links <path> [--direction to|from|both]` - Show edges to/from a file

</details>

<details>
<summary><strong>wksc link</strong> - Resource edge operations</summary>

- `status` - Get health and statistics for links collection
- `show <uri> [--direction to|from|both]` - Show edges connected to URI
- `check <path> [--parser]` - Check links in file
- `sync <path> [--parser] [--recursive] [--remote]` - Sync links to database

</details>

<details>
<summary><strong>wksc daemon</strong> - Daemon runtime</summary>

- `status` - Check daemon status
- `start [--restrict] [--blocking]` - Start daemon
- `stop` - Stop daemon
- `clear` - Clear daemon logs (only if stopped)

</details>

<details>
<summary><strong>wksc service</strong> - System service</summary>

- `status` - Check service status
- `start` / `stop` - Start/stop service
- `install [--restrict]` - Install system service
- `uninstall` - Uninstall system service

</details>

<details>
<summary><strong>wksc config</strong> - Configuration</summary>

- `list` - List configuration sections
- `show <section>` - Show section configuration
- `version` - Show WKS version

</details>

<details>
<summary><strong>wksc database</strong> - Database operations</summary>

- `list` - List all databases
- `show <database> [--query] [--limit]` - Show database contents
- `reset <database>` - Reset (clear) database
- `prune <database> [--remote]` - Prune stale entries

</details>

<details>
<summary><strong>wksc mcp</strong> - MCP server</summary>

- `list` - List MCP installations
- `install <name> [--type] [--settings-path]` - Install MCP server
- `uninstall <name>` - Uninstall MCP server
- `run [--direct]` - Run MCP server

</details>

**Global Options**: `--version` / `-v`, `--display json|yaml` (default: yaml), `--help` / `-h`

## Install

### Requirements

- Python 3.10+
- MongoDB 4.0+
- macOS/Linux

### From Source

```bash
# Clone and setup
git clone https://github.com/wawiesel/wks.git
cd 2025-WKS

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e '.[all]'

# Optional: Install docling for PDF/Office transformation
pipx runpip wksc install docling
```

# Initialize configuration
wksc config

# Start background service
wksc service start

# Check status
wksc service status

# Sync vault links
wksc vault sync

# View vault links
wksc vault links ~/vault/Note.md
```

## MCP Integration

Install for AI assistants:
```bash
wksc mcp install  # Install for all clients
wksc mcp install --client cursor --client claude
```

Available tools: `wksm_*` (see [docs/specifications/wks.md](docs/specifications/wks.md) for details)

## Architecture

The system's architecture is designed in layers, with core functionality currently implemented and under revision up to the **Indexing Layer** as described in the specifications.

See [docs/specifications/wks.md](docs/specifications/wks.md) for the complete system specification.

**Key Layers (Implemented & Under Revision)**:
- **Monitor Layer**: Filesystem state tracking
- **Vault Layer**: Knowledge graph links
- **Transform Layer**: Document conversion
- **Diff Layer**: File comparison engines
- **Service Layer**: Background daemon
- **Index Layer**: Building towards comprehensive search indices (conceptualized in SPEC.md)

## Documentation

-   **[CONTRIBUTING.md](CONTRIBUTING.md)**: Development & Testing Guide
-   **[docker/README.md](docker/README.md)**: CI Docker Image Guide
-   **[docs/specifications/wks.md](docs/specifications/wks.md)**: The complete system specification and architectural overview.
-   **[docs/campaigns/NEXT.md](docs/campaigns/NEXT.md)**: Current development priorities and high-level roadmap.
-   **[AGENTS.md](AGENTS.md)**: Specific directives and guidelines for AI agents working on this project.
-   **[LICENSE.txt](LICENSE.txt)**: Project license details.
