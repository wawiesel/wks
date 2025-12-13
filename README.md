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
| **api**   |      99 |  8,787 |      306,789 |   49,943 |      31.4% |
| **cli**   |      11 |    990 |       34,215 |    6,100 |       3.8% |
| **mcp**   |       9 |    457 |       16,368 |    3,188 |       2.0% |
| **utils** |      10 |    472 |       13,981 |    1,417 |       0.9% |
| **Total** |     129 | 10,706 |      371,353 |   60,648 |      38.2% |

### Testing Statistics

| Type                  |   Files |   LOC |   Characters |   Tokens |   % Tokens |
|-----------------------|--------:|------:|-------------:|---------:|-----------:|
| **Unit Tests**        |      43 | 3,534 |      121,170 |   21,291 |      13.4% |
| **Integration Tests** |      10 | 1,074 |       34,707 |    6,933 |       4.4% |
| **Smoke Tests**       |       3 |   332 |       10,175 |    1,737 |       1.1% |
| **Total**             |      56 | 4,940 |      166,052 |   29,961 |      18.9% |

### Documentation Size Summary

| Category                    |   Files |   LOC |   Characters |   Tokens |   % Tokens |
|-----------------------------|--------:|------:|-------------:|---------:|-----------:|
| **User Documentation**      |       8 |   375 |       13,332 |    3,332 |       2.1% |
| **Developer Documentation** |      47 | 3,434 |      146,728 |   36,675 |      23.1% |
| **Specifications**          |      19 | 1,479 |       65,344 |   16,336 |      10.3% |
| **Total**                   |      74 | 5,288 |      225,404 |   56,343 |      35.5% |

### Infrastructure Summary

| Type             |   Files |   LOC |   Characters |   Tokens |   % Tokens |
|------------------|--------:|------:|-------------:|---------:|-----------:|
| **CI/CD**        |       4 |   209 |        5,436 |    1,359 |       0.9% |
| **Build/Config** |       5 |   200 |        5,522 |    1,378 |       0.9% |
| **Scripts**      |      12 | 1,341 |       44,859 |    9,221 |       5.8% |
| **Total**        |      21 | 1,750 |       55,817 |   11,958 |       7.5% |

**Mutation Testing**: Tests the quality of our test suite by introducing small changes (mutations) to the code and verifying that existing tests catch them. A score of 91.6% means 91.6% of mutations are killed by our tests, indicating strong test coverage and quality.

**Test Statistics**: 225 tests across 51 test files.


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
