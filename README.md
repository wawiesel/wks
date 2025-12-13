# WKS

![Coverage](https://img.shields.io/badge/coverage-49.8%25-red)
![Mutation Score](https://img.shields.io/badge/mutation-91.6%25-brightgreen)
![Tests](https://img.shields.io/badge/tests-225-passing-brightgreen)
![Python](https://img.shields.io/badge/python-3.10+-blue)
![Status](https://img.shields.io/badge/status-alpha-orange)

## Status
- Alpha: monitor, vault, transform, diff layers are under active development; CLI and MCP may change without notice.
- Upcoming priorities and ideas: [docs/campaigns/NEXT.md](docs/campaigns/NEXT.md).

## Code Quality Metrics

| Metric              |   Value |   Target | Status          |
|---------------------|--------:|---------:|----------------:|
| **Code Coverage**   |   49.8% |     100% | ⚠️ Below Target |
| **Mutation Kill %** |   91.6% |     ≥90% | ✅ Pass          |

### Source Size Statistics

| Section   |   Files |    LOC |   Characters |   Tokens |   % Tokens |
|-----------|--------:|-------:|-------------:|---------:|-----------:|
| **api**   |     101 |  9,124 |      318,983 |   51,848 |      31.7% |
| **cli**   |      11 |  1,015 |       34,491 |    6,197 |       3.8% |
| **mcp**   |       9 |    483 |       17,049 |    3,354 |       2.1% |
| **utils** |      10 |    472 |       13,981 |    1,417 |       0.9% |
| **Total** |     131 | 11,094 |      384,504 |   62,816 |      38.4% |

### Testing Statistics

| Type                  |   Files |   LOC |   Characters |   Tokens |   % Tokens |
|-----------------------|--------:|------:|-------------:|---------:|-----------:|
| **Unit Tests**        |      43 | 3,540 |      121,478 |   21,302 |      13.0% |
| **Integration Tests** |      11 | 1,205 |       39,047 |    7,581 |       4.6% |
| **Smoke Tests**       |       3 |   332 |       10,171 |    1,737 |       1.1% |
| **Total**             |      57 | 5,077 |      170,696 |   30,620 |      18.7% |

### Documentation Size Summary

| Category                    |   Files |   LOC |   Characters |   Tokens |   % Tokens |
|-----------------------------|--------:|------:|-------------:|---------:|-----------:|
| **User Documentation**      |       8 |   375 |       13,332 |    3,332 |       2.0% |
| **Developer Documentation** |      48 | 3,476 |      148,936 |   37,226 |      22.8% |
| **Specifications**          |      19 | 1,479 |       65,344 |   16,336 |      10.0% |
| **Total**                   |      75 | 5,330 |      227,612 |   56,894 |      34.8% |

### Infrastructure Summary

| Type             |   Files |   LOC |   Characters |   Tokens |   % Tokens |
|------------------|--------:|------:|-------------:|---------:|-----------:|
| **CI/CD**        |       5 |   275 |        7,493 |    1,873 |       1.1% |
| **Build/Config** |       5 |   201 |        5,613 |    1,401 |       0.9% |
| **Scripts**      |      12 | 1,453 |       49,261 |    9,847 |       6.0% |
| **Total**        |      22 | 1,929 |       62,367 |   13,121 |       8.0% |

**Mutation Testing**: Tests the quality of our test suite by introducing small changes (mutations) to the code and verifying that existing tests catch them. A score of 91.6% means 91.6% of mutations are killed by our tests, indicating strong test coverage and quality.

**Test Statistics**: 225 tests across 52 test files.


## Overview

WKS provides intelligent filesystem monitoring, vault link tracking, and document transformation capabilities. Built as a layered architecture with MongoDB backend and Model Context Protocol (MCP) integration for AI assistants.

**Important Note**: WKS is currently in **alpha development status** and is **not yet ready for external users**. Our immediate focus is on comprehensive revision and ensuring 100% test coverage across existing features.

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

-   **[CONTRIBUTING.md](CONTRIBUTING.md)**: Your primary guide for contributing to WKS, covering setup, coding standards, Git commit guidelines, quality checks, and testing procedures.
-   **[docs/specifications/wks.md](docs/specifications/wks.md)**: The complete system specification and architectural overview.
-   **[docs/campaigns/NEXT.md](docs/campaigns/NEXT.md)**: Current development priorities and high-level roadmap.
-   **[AGENTS.md](AGENTS.md)**: Specific directives and guidelines for AI agents working on this project.
-   **[LICENSE.txt](LICENSE.txt)**: Project license details.
