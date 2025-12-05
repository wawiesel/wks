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
-   **Config-First**: All configuration values must be defined in `~/.wks/config.json`. **Defaults in code are an error** - if a value is missing from the config file, validation must fail immediately.
-   **Override Anywhere**: CLI and MCP can override any config parameter.
-   **Engine Plugins**: Each layer supports multiple engines with dedicated configuration.
-   **Zero Duplication**: CLI and MCP share identical business logic via controllers.
-   **Strict Validation**: Configuration access is centralized through **dataclasses** with strict validation on load. Fail immediately if data is missing or invalid. All required fields must be present in the config file - no code-level defaults are permitted.
-   **No Hedging**: Remove fallback logic; no silent defaults or implicit substitutions. Fail fast and visibly. If a configuration value is missing, raise a validation error rather than using a default.

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

## What is a Specification?

A specification describes **WHAT** the system does, not **HOW** it is implemented. It defines:

- **Interfaces**: Public APIs, command structures, and data formats
- **Behavior**: How the system responds to inputs and what outputs it produces
- **Requirements**: What must be present, what must be validated, and what must fail
- **Configuration**: What configuration is required and how it is structured
- **Principles**: Design principles and constraints that implementations must follow

**Note**: The configuration file (`~/.wks/config.json`), MCP commands (`wksm_*`), and CLI commands (`wksc *`) are all part of the public interface and must be fully specified. These are the contracts that users and AI agents interact with, and they must remain stable even if the implementation changes.

A specification is **not**:
- An implementation guide or tutorial
- A description of specific code files, classes, or functions
- A step-by-step guide for adding features
- A reference to specific implementation details

## What Should Not Be in Specifications

Specification documents must **not** contain:

- **Implementation details**: Specific file names, class names, function names, or code locations
- **Step-by-step implementation instructions**: How to add features, modify code, or implement backends
- **Code examples**: Actual code snippets showing implementation (configuration examples are acceptable)
- **Directory structures**: Specific file paths or directory layouts
- **Specific technology requirements**: References to specific libraries, frameworks, or tools (unless they are part of the interface)
- **Backend-specific details**: Implementation details for specific backends (use examples, not requirements)
- **Internal architecture**: How the system is structured internally (only describe the public interface)

**Examples of what to include**:
- "The database layer provides collection operations and query functions" ✓
- "Configuration must be validated and fail immediately if required fields are missing" ✓
- "The monitor layer calculates priority based on path structure and configured weights" ✓

**Examples of what not to include**:
- "The `DbCollection` class in `wks/api/db/DbCollection.py` provides..." ✗
- "To add a new backend, create `_Impl.py` and `_DbConfigData.py` in `_<type>/`..." ✗
- "Use `Field(...)` for required fields and `Field(default=...)` for optional..." ✗

Specifications should remain valid even if the implementation is completely rewritten using different technologies, file structures, or design patterns.
