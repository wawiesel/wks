# WKS

![Coverage](https://img.shields.io/badge/coverage-49.8%25-red)
![Mutation Score](https://img.shields.io/badge/mutation-91.6%25-brightgreen)
![Tests](https://img.shields.io/badge/tests-226-passing-brightgreen)
![Python](https://img.shields.io/badge/python-3.10+-blue)
![Status](https://img.shields.io/badge/status-alpha-orange)
![Docker Freshness](https://github.com/wawiesel/wks/actions/workflows/check-image-freshness.yml/badge.svg)

## Status
- Alpha: monitor, vault, transform, diff layers are under active development; CLI and MCP may change without notice.
- Upcoming priorities and ideas: [docs/campaigns/NEXT.md](docs/campaigns/NEXT.md).

## Code Quality Metrics

| Metric               |   Value |     Target | Status          |
|----------------------|--------:|-----------:|----------------:|
| **Code Coverage**    |   49.8% |       100% | ⚠️ Below Target |
| **Mutation Kill %**  |   91.6% |       ≥90% | ✅ Pass          |
| **Docker Freshness** |      v1 | Up to date | ✅ Pass          |

### Source Size Statistics

| Section   |   Files |    LOC |   Characters |   Tokens |   % Tokens |
|-----------|--------:|-------:|-------------:|---------:|-----------:|
<<<<<<< HEAD
| **api**   |     101 |  9,186 |      322,897 |   52,267 |      31.4% |
| **cli**   |      11 |  1,015 |       34,491 |    6,197 |       3.7% |
| **mcp**   |       9 |    483 |       17,049 |    3,354 |       2.0% |
| **utils** |      10 |    472 |       13,981 |    1,417 |       0.9% |
| **Total** |     131 | 11,156 |      388,418 |   63,235 |      38.0% |
=======
| **api**   |     101 |  9,186 |      322,897 |   52,267 |      33.0% |
| **cli**   |      11 |  1,015 |       34,491 |    6,197 |       3.9% |
| **mcp**   |       9 |    483 |       17,049 |    3,354 |       2.1% |
| **utils** |      10 |    472 |       13,981 |    1,417 |       0.9% |
| **Total** |     131 | 11,156 |      388,418 |   63,235 |      40.0% |
>>>>>>> 179e30c (docs: finalize cleanup (campaigns, docker docs, readme stats))

### Testing Statistics

| Type                  |   Files |   LOC |   Characters |   Tokens |   % Tokens |
|-----------------------|--------:|------:|-------------:|---------:|-----------:|
<<<<<<< HEAD
| **Unit Tests**        |      43 | 3,552 |      122,071 |   21,353 |      12.8% |
| **Integration Tests** |      12 | 1,566 |       52,600 |    9,482 |       5.7% |
| **Smoke Tests**       |       3 |   332 |       10,175 |    1,737 |       1.0% |
| **Total**             |      58 | 5,450 |      184,846 |   32,572 |      19.6% |
=======
| **Unit Tests**        |      43 | 3,552 |      122,071 |   21,353 |      13.5% |
| **Integration Tests** |      12 | 1,555 |       52,094 |    9,432 |       6.0% |
| **Smoke Tests**       |       3 |   332 |       10,175 |    1,737 |       1.1% |
| **Total**             |      58 | 5,439 |      184,340 |   32,522 |      20.6% |
>>>>>>> 179e30c (docs: finalize cleanup (campaigns, docker docs, readme stats))

### Documentation Size Summary

| Category                    |   Files |   LOC |   Characters |   Tokens |   % Tokens |
|-----------------------------|--------:|------:|-------------:|---------:|-----------:|
<<<<<<< HEAD
| **User Documentation**      |       7 |   228 |        7,065 |    1,766 |       1.1% |
| **Developer Documentation** |      48 | 3,478 |      149,119 |   37,272 |      22.4% |
| **Specifications**          |      19 | 1,479 |       65,344 |   16,336 |       9.8% |
| **Total**                   |      74 | 5,185 |      221,528 |   55,374 |      33.3% |
=======
| **User Documentation**      |       8 |   375 |       13,332 |    3,332 |       2.1% |
| **Developer Documentation** |      43 | 2,568 |      112,738 |   28,178 |      17.8% |
| **Specifications**          |      19 | 1,479 |       65,344 |   16,336 |      10.3% |
| **Total**                   |      70 | 4,422 |      191,414 |   47,846 |      30.2% |
>>>>>>> 179e30c (docs: finalize cleanup (campaigns, docker docs, readme stats))

### Infrastructure Summary

| Type             |   Files |   LOC |   Characters |   Tokens |   % Tokens |
|------------------|--------:|------:|-------------:|---------:|-----------:|
<<<<<<< HEAD
| **CI/CD**        |       6 |   448 |       13,869 |    3,467 |       2.1% |
| **Build/Config** |       5 |   211 |        5,831 |    1,457 |       0.9% |
| **Scripts**      |      12 | 1,509 |       51,499 |   10,267 |       6.2% |
| **Total**        |      23 | 2,168 |       71,199 |   15,191 |       9.1% |
=======
| **CI/CD**        |       6 |   418 |       13,105 |    3,276 |       2.1% |
| **Build/Config** |       5 |   211 |        5,805 |    1,450 |       0.9% |
| **Scripts**      |      12 | 1,453 |       49,261 |    9,847 |       6.2% |
| **Total**        |      23 | 2,082 |       68,171 |   14,573 |       9.2% |
>>>>>>> 179e30c (docs: finalize cleanup (campaigns, docker docs, readme stats))

**Mutation Testing**: Tests the quality of our test suite by introducing small changes (mutations) to the code and verifying that existing tests catch them. A score of 91.6% means 91.6% of mutations are killed by our tests, indicating strong test coverage and quality.

**Test Statistics**: 226 tests across 53 test files.


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

-   **[CONTRIBUTING.md](CONTRIBUTING.md)**: Development & Testing Guide
-   **[docker/README.md](docker/README.md)**: CI Docker Image Guide
-   **[docs/specifications/wks.md](docs/specifications/wks.md)**: The complete system specification and architectural overview.
-   **[docs/campaigns/NEXT.md](docs/campaigns/NEXT.md)**: Current development priorities and high-level roadmap.
-   **[AGENTS.md](AGENTS.md)**: Specific directives and guidelines for AI agents working on this project.
-   **[LICENSE.txt](LICENSE.txt)**: Project license details.
