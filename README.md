# WKS

![Coverage](https://img.shields.io/badge/coverage-0%25-red)
![Mutation Score](https://img.shields.io/badge/mutation-71.8%25-red)
![Traceability](https://img.shields.io/badge/traceability-100.0%25-brightgreen)
![Tests](https://img.shields.io/badge/tests-491_passing-brightgreen)
![Python](https://img.shields.io/badge/python-3.10+-blue)
![Status](https://img.shields.io/badge/status-alpha-orange)
![Docker Freshness](https://github.com/wawiesel/wks/actions/workflows/check-image-freshness.yml/badge.svg)

## Status
- Alpha: monitor, vault, transform, diff layers are under active development; CLI and MCP may change without notice.
- Upcoming priorities and ideas: [docs/campaigns/NEXT.md](docs/campaigns/NEXT.md).

## Code Quality Metrics

| Metric               |   Value |     Target | Status          |
|----------------------|--------:|-----------:|----------------:|
| **Code Coverage**    |      0% |       100% | ⚠️ Below Target |
| **Mutation Kill %**  |   71.8% |       ≥90% | ⚠️ Below Target |
| **Traceability**     |  100.0% |       100% | ✅ Pass          |
| **Docker Freshness** |      v1 | Up to date | ✅ Pass          |

### Source Size Statistics

| Section   |   Files |    LOC |   Characters |   Tokens |   % Tokens |
|-----------|--------:|-------:|-------------:|---------:|-----------:|
<<<<<<< HEAD
| **api**   |     174 | 11,661 |      411,290 |   64,962 |      33.3% |
| **cli**   |      20 |  1,313 |       46,319 |    8,790 |       4.5% |
| **mcp**   |       9 |    518 |       18,440 |    3,457 |       1.8% |
| **utils** |      21 |    669 |       20,623 |    2,663 |       1.4% |
| **Total** |     224 | 14,161 |      496,672 |   79,872 |      41.0% |
=======
| **api**   |     174 | 11,661 |      411,294 |   64,962 |      33.4% |
| **cli**   |      20 |  1,313 |       46,319 |    8,790 |       4.5% |
| **mcp**   |       9 |    518 |       18,440 |    3,457 |       1.8% |
| **utils** |      21 |    669 |       20,623 |    2,663 |       1.4% |
| **Total** |     224 | 14,161 |      496,676 |   79,872 |      41.1% |
>>>>>>> 26c01ab (Update)

### Testing Statistics

| Type                  |   Files |    LOC |   Characters |   Tokens |   % Tokens |
|-----------------------|--------:|-------:|-------------:|---------:|-----------:|
<<<<<<< HEAD
| **Unit Tests**        |      86 |  9,008 |      308,621 |   54,746 |      28.1% |
| **Integration Tests** |      13 |  1,544 |       52,098 |    9,481 |       4.9% |
| **Smoke Tests**       |       7 |    352 |       11,844 |    2,049 |       1.1% |
| **Total**             |     106 | 10,904 |      372,563 |   66,276 |      34.0% |
=======
| **Unit Tests**        |      86 |  9,008 |      308,621 |   54,746 |      28.2% |
| **Integration Tests** |      13 |  1,544 |       52,098 |    9,481 |       4.9% |
| **Smoke Tests**       |       7 |    352 |       11,844 |    2,049 |       1.1% |
| **Total**             |     106 | 10,904 |      372,563 |   66,276 |      34.1% |
>>>>>>> 26c01ab (Update)

### Documentation Size Summary

| Category                    |   Files |   LOC |   Characters |   Tokens |   % Tokens |
|-----------------------------|--------:|------:|-------------:|---------:|-----------:|
| **User Documentation**      |       7 |   228 |        7,065 |    1,766 |       0.9% |
<<<<<<< HEAD
| **Developer Documentation** |      46 | 2,827 |      113,382 |   28,337 |      14.5% |
| **Specifications**          |       0 |     0 |            0 |        0 |       0.0% |
| **Total**                   |      53 | 3,055 |      120,447 |   30,103 |      15.4% |
=======
| **Developer Documentation** |      46 | 2,768 |      111,199 |   27,791 |      14.3% |
| **Specifications**          |       0 |     0 |            0 |        0 |       0.0% |
| **Total**                   |      53 | 2,996 |      118,264 |   29,557 |      15.2% |
>>>>>>> 26c01ab (Update)

### Infrastructure Summary

| Type             |   Files |   LOC |   Characters |   Tokens |   % Tokens |
|------------------|--------:|------:|-------------:|---------:|-----------:|
<<<<<<< HEAD
| **CI/CD**        |       4 |   379 |       11,469 |    2,867 |       1.5% |
| **Build/Config** |       5 |   167 |        3,889 |      970 |       0.5% |
| **Scripts**      |      21 | 2,230 |       75,523 |   14,762 |       7.6% |
| **Total**        |      30 | 2,776 |       90,881 |   18,599 |       9.5% |
=======
| **CI/CD**        |       4 |   379 |       11,489 |    2,872 |       1.5% |
| **Build/Config** |       5 |   167 |        3,890 |      971 |       0.5% |
| **Scripts**      |      21 | 2,230 |       75,571 |   14,774 |       7.6% |
| **Total**        |      30 | 2,776 |       90,950 |   18,617 |       9.6% |
>>>>>>> 26c01ab (Update)

**Mutation Testing**: Tests the quality of our test suite by introducing small changes (mutations) to the code and verifying that existing tests catch them. A score of 71.8% means 71.8% of introduced mutations were successfully killed by the test suite.

**Test Statistics**: 491 tests across 100 test files.

### Per-Domain Quality

| Domain    |   Coverage |   Mutation % |   Killed/Total |
|-----------|------------|--------------|----------------|
| cat       |        94% |          N/A |            0/0 |
| config    |       100% |          N/A |            0/0 |
| daemon    |        83% |          N/A |            0/0 |
| database  |        91% |          N/A |            0/0 |
| diff      |         0% |          N/A |            0/0 |
| link      |        98% |          N/A |            0/0 |
| log       |        94% |          N/A |            0/0 |
| mcp       |        99% |          N/A |            0/0 |
| monitor   |        99% |          N/A |            0/0 |
| service   |        69% |          N/A |            0/0 |
| transform |        88% |          N/A |            0/0 |
| utils     |       100% |          N/A |            0/0 |
| vault     |       100% |          72% |       887/1235 |


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
-   **[docs/campaigns/NEXT.md](docs/campaigns/NEXT.md)**: Current development priorities and high-level roadmap.
-   **[AGENTS.md](AGENTS.md)**: Specific directives and guidelines for AI agents working on this project.
-   **[LICENSE.txt](LICENSE.txt)**: Project license details.
