# WKS (Wieselquist Knowledge System)

A layered architecture for filesystem monitoring, knowledge graph management, and semantic indexing.

**Primary Interface**: The **MCP Server** is the source of truth for all capabilities, allowing AI agents to fully control the system.
**Secondary Interface**: The `wksc` CLI provides human-friendly equivalents for all MCP tools.

## Architecture Overview

WKS is built as a stack of independent, composable layers:

```
                    ┌──────────────────────────────────────────┐
                    │  Patterns Layer                          │
                    │  AI agents executing organizational      │
                    │  patterns for knowledge management       │
                    └──────────────────────────────────────────┘
                                      ↓
                    ┌──────────────────────────────────────────┐
                    │  Search Layer                            │
                    │  Semantic + keyword search combining     │
                    │  multiple indices with weighted results  │
                    └──────────────────────────────────────────┘
                                      ↓
                    ┌──────────────────────────────────────────┐
                    │  Diff Layer                              │
                    │  Pluggable comparison engines            │
                    │  (myers, bsdiff3, ...)                   │
                    └──────────────────────────────────────────┘
                                      ↓
                    ┌──────────────────────────────────────────┐
                    │  Transform Layer                         │
                    │  Multi-engine document conversion        │
                    │  Docling (PDF/DOCX/PPTX → Markdown)      │
                    │  Extensible converter plugin system      │
                    └──────────────────────────────────────────┘
                                      ↓
                    ┌──────────────────────────────────────────┐
                    │  Vault Layer                             │
                    │  Knowledge graph link tracking           │
                    │  Obsidian + extensible vault types       │
                    │  Symlinks: _links/<machine>/             │
                    └──────────────────────────────────────────┘
                                      ↓
                    ┌──────────────────────────────────────────┐
                    │  Monitor Layer                           │
                    │  Filesystem tracking + priority scoring  │
                    │  Paths, checksums, modification times    │
                    └──────────────────────────────────────────┘
```

## Design Principles

-   **Interfaces**: Support **only CLI and MCP** interfaces. All other modes are unsupported.
-   **Config-First**: All defaults defined in `~/.wks/config.json`.
-   **Override Anywhere**: CLI and MCP can override any config parameter.
-   **Engine Plugins**: Each layer supports multiple engines with dedicated configuration.
-   **Zero Duplication**: CLI and MCP share identical business logic via controllers.
-   **Strict Validation**: Configuration access is centralized through **dataclasses** with strict validation on load. Fail immediately if data is missing or invalid.
-   **No Hedging**: Remove fallback logic; no silent defaults or implicit substitutions. Fail fast and visibly.

## Layer Specifications

Detailed specifications for each component:

*   **[Configuration](config.md)**: System-wide configuration structure.
*   **[Monitor Layer](monitor.md)**: Filesystem tracking and priority scoring.
*   **[Vault Layer](vault.md)**: Knowledge graph and link management.
*   **[Transform Layer](transform.md)**: Document conversion (PDF/Office to Markdown).
*   **[Diff Layer](diff.md)**: Content comparison engines.
*   **[Index Layer](index_layer.md)**: Searchable indices and embedding management.
*   **[Search Layer](search.md)**: Query execution and ranking.
*   **[Patterns Layer](patterns.md)**: Agentic workflows and automation.
*   **[Infrastructure](infrastructure.md)**: Database, Service Daemon, and MCP Server.
*   **[Quality & Standards](quality.md)**: Code metrics, error handling, and CLI guidelines.
