# WKS

![Coverage](https://img.shields.io/badge/coverage-84.0%25-yellow)
![Mutation Score](https://img.shields.io/badge/mutation-70.3%25-red)
![Traceability](https://img.shields.io/badge/traceability-100.0%25-brightgreen)
![Tests](https://img.shields.io/badge/tests-557_passing-brightgreen)
![Python](https://img.shields.io/badge/python-3.10+-blue)
![Status](https://img.shields.io/badge/status-alpha-orange)
![Docker Freshness](https://github.com/wawiesel/wks/actions/workflows/check-image-freshness.yml/badge.svg)

## Status
- Alpha: monitor, vault, transform, diff layers are under active development; CLI and MCP may change without notice.
- Upcoming priorities and ideas: [NEXT.md](NEXT.md).

## Code Quality Metrics

| Metric               |   Value |     Target | Status          |
|----------------------|--------:|-----------:|----------------:|
| **Code Coverage**    |   84.0% |       100% | ⚠️ Below Target |
| **Mutation Kill %**  |   70.3% |       ≥90% | ⚠️ Below Target |
| **Traceability**     |  100.0% |       100% | ✅ Pass          |
| **Docker Freshness** |      v1 | Up to date | ✅ Pass          |

### Source Size Statistics

| Section   |   Files |    LOC |   Characters |   Tokens |   % Tokens |
|-----------|--------:|-------:|-------------:|---------:|-----------:|
| **api**   |     184 | 12,075 |      427,347 |   67,372 |      33.3% |
| **cli**   |      25 |  1,534 |       52,828 |    9,671 |       4.8% |
| **mcp**   |       9 |    516 |       18,383 |    3,458 |       1.7% |
| **utils** |       0 |      0 |            0 |        0 |       0.0% |
| **Total** |     218 | 14,125 |      498,558 |   80,501 |      39.8% |

### Testing Statistics

| Type                  |   Files |    LOC |   Characters |   Tokens |   % Tokens |
|-----------------------|--------:|-------:|-------------:|---------:|-----------:|
| **Unit Tests**        |      88 | 10,163 |      350,188 |   61,203 |      30.2% |
| **Integration Tests** |      13 |  1,548 |       52,064 |    9,510 |       4.7% |
| **Smoke Tests**       |       7 |    352 |       11,844 |    2,049 |       1.0% |
| **Total**             |     108 | 12,063 |      414,096 |   72,762 |      35.9% |

### Documentation Size Summary

| Category                    |   Files |   LOC |   Characters |   Tokens |   % Tokens |
|-----------------------------|--------:|------:|-------------:|---------:|-----------:|
| **User Documentation**      |       7 |   228 |        7,065 |    1,766 |       0.9% |
| **Developer Documentation** |      43 | 2,815 |      112,935 |   28,227 |      13.9% |
| **Specifications**          |       0 |     0 |            0 |        0 |       0.0% |
| **Total**                   |      50 | 3,043 |      120,000 |   29,993 |      14.8% |

### Infrastructure Summary

| Type             |   Files |   LOC |   Characters |   Tokens |   % Tokens |
|------------------|--------:|------:|-------------:|---------:|-----------:|
| **CI/CD**        |       4 |   380 |       11,456 |    2,864 |       1.4% |
| **Build/Config** |       5 |   168 |        3,904 |      974 |       0.5% |
| **Scripts**      |      21 | 2,322 |       79,779 |   15,333 |       7.6% |
| **Total**        |      30 | 2,870 |       95,139 |   19,171 |       9.5% |

**Mutation Testing**: Tests the quality of our test suite by introducing small changes (mutations) to the code and verifying that existing tests catch them. A score of 70.3% means 70.3% of introduced mutations were successfully killed by the test suite.

**Test Statistics**: 557 tests across 102 test files.

### Per-Domain Quality

| Domain    |   Coverage |   Mutation % |   Killed/Total |
|-----------|------------|--------------|----------------|
| cat       |        94% |          73% |         73/100 |
| config    |        98% |          71% |        234/329 |
| daemon    |        84% |          67% |        237/355 |
| database  |        90% |          71% |        450/635 |
| diff      |         0% |            — |              — |
| link      |        97% |          67% |       812/1217 |
| log       |        94% |          67% |        367/547 |
| mcp       |        97% |          57% |        225/398 |
| monitor   |        99% |          68% |      1151/1702 |
| service   |        92% |          86% |         99/115 |
| transform |        95% |          83% |        745/898 |
| utils     |         0% |            — |              — |
| vault     |       100% |          73% |       961/1316 |


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

- Python 3.12, 3.13, or 3.14
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

Available tools: `wksm_*` (see [qa/specs/wks.md](qa/specs/wks.md) for details)

## Architecture

The system's architecture is designed in layers, with core functionality currently implemented and under revision up to the **Indexing Layer** as described in the specifications.

See [qa/specs/wks.md](qa/specs/wks.md) for the complete system specification.

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
-   **[qa/specs/wks.md](qa/specs/wks.md)**: The complete system specification and architectural overview.
-   **[NEXT.md](NEXT.md)**: Current development priorities and high-level roadmap.
-   **[AGENTS.md](AGENTS.md)**: Specific directives and guidelines for AI agents working on this project.
-   **[LICENSE.txt](LICENSE.txt)**: Project license details.
