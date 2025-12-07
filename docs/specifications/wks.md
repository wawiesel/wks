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
                                      ↓
                    ┌──────────────────────────────────────────┐
                    │  Database Layer                          │
                    │  Database abstraction with pluggable     │
                    │  backends (mongo, mongomock, ...)        │
                    └──────────────────────────────────────────┘
                                      ↓
                    ┌──────────────────────────────────────────┐
                    │  Configuration Layer                     │
                    │  System-wide configuration management    │
                    │  Config file validation and loading      │
                    └──────────────────────────────────────────┘
```

## Design Principles

-   **Interfaces**: Support **only CLI and MCP** interfaces. All other modes are unsupported.
-   **API-First Design**: All business logic lives in the API layer. CLI and MCP are thin wrappers that call the same API functions. There is zero duplication between CLI and MCP - they share identical business logic.
-   **CLI/MCP Symmetry**: Every CLI command (`wksc <domain> <command>`) has a corresponding MCP tool (`wksm_<domain>_<command>`) that uses the same underlying API function. Both interfaces provide the same functionality with different presentation layers.
-   **Config-First**: All configuration values must be defined in `{WKS_HOME}/config.json` (where `WKS_HOME` defaults to `~/.wks` if not set via environment variable). **Defaults in code are an error** - if a value is missing from the config file, validation must fail immediately.
-   **Override Anywhere**: CLI and MCP can override any config parameter.
-   **Engine Plugins**: Each layer supports multiple engines with dedicated configuration.
-   **Strict Validation**: Configuration access is centralized through **dataclasses** with strict validation on load. Fail immediately if data is missing or invalid. All required fields must be present in the config file - no code-level defaults are permitted.
-   **No Hedging**: Remove fallback logic; no silent defaults or implicit substitutions. Fail fast and visibly. If a configuration value is missing, raise a validation error rather than using a default.
-   **Structured Error Handling**: Errors are collected and reported together rather than failing immediately. System behavior is deterministic with no optional or hidden recovery logic.

## CLI Global Options

All CLI commands support the following global options:

### `--display` / `-d` (Output Format)

Controls the output format for structured data. Available formats:
- `yaml` (default) - YAML format with syntax highlighting in interactive terminals
- `json` - JSON format with syntax highlighting in interactive terminals

When output is redirected to a file, both formats produce valid, unformatted output suitable for parsing.

**Examples**:
```bash
wksc monitor status --display json
wksc database show monitor -d yaml
wksc config monitor > config.yaml  # Valid YAML when redirected
```

### `--live` / `-l` (Live Updates)

Continuously runs the command every N seconds, updating the display in place. This is a CLI-only feature (not available in MCP).

**Usage**: `--live <seconds>` or `-l <seconds>`

**Behavior**:
- Command executes repeatedly at the specified interval
- Display updates in place using a live terminal interface
- Shows "Live mode (CNTL-C to end)" message at the bottom
- Press Ctrl+C to exit

**Examples**:
```bash
wksc monitor status --live 5    # Update every 5 seconds
wksc database show monitor -l 2       # Update every 2 seconds
```

**Note**: The `--live` option is handled at the CLI layer and does not affect the API or MCP interfaces.

## Command Execution Pattern

All commands (CLI and MCP) follow a unified 4-step execution pattern that provides immediate feedback, progress tracking, and structured results:

1. **Announce**: Immediately output action description
   - CLI: Status message on STDERR
   - MCP: Immediate response with status message or `job_id` for long-running operations

2. **Progress**: Display progress indicator with time estimate
   - CLI: Progress bar on STDERR with time estimate
   - MCP: Progress notifications (`notifications/progress`) with `job_id`, progress percentage, message, and `estimated_remaining_seconds`
   - Time estimates are provided when progress starts (Step 2), not in the initial announcement, ensuring estimates are based on actual work being performed

3. **Result**: Report completion status and any issues
   - CLI: Success/error message on STDERR
   - MCP: Result notification messages in final response

4. **Output**: Display the final structured output
   - CLI: Structured data on STDOUT (YAML or JSON based on `--display` option)
   - MCP: Result notification data (`notifications/tool_result` for async operations, or direct result for synchronous operations)

**Unified Pattern**: The same 4-step pattern works for both CLI and MCP, with different display mechanisms. This ensures consistent behavior and user experience across both interfaces.

### Long-Running Operations (MCP Async)

For operations that may take significant time, MCP supports asynchronous execution:

- **Immediate Response**: Tool returns immediately with `job_id` and status ("queued" or "running")
- **Progress Notifications**: During execution, the server sends `notifications/progress` messages with:
  - `job_id`: Correlates notifications to the original request
  - `progress`: 0.0-1.0 indicating completion percentage
  - `message`: Human-readable status message
  - `estimated_remaining_seconds`: Time estimate (provided when progress starts)
  - `timestamp`: ISO 8601 timestamp
- **Final Result**: Server sends `notifications/tool_result` with:
  - `job_id`: Correlates to the original request
  - `result`: Complete result with `success`, `data`, and `messages` fields
  - `timestamp`: ISO 8601 timestamp

**Client Requirements**: MCP clients must handle immediate responses with `job_id`, listen for progress and result notifications, correlate by `job_id`, and display progress updates to users.

**Error Handling**: If an error occurs during async execution, the final `notifications/tool_result` contains an error result with `success: false` and error details in the `messages` field.

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
*   **[Database](database.md)**: Database abstraction and collection operations.
*   **[Daemon](daemon.md)**: Background service for filesystem monitoring and knowledge graph maintenance.
*   **[MCP Installation Management](mcp.md)**: Commands for managing WKS MCP server installations across various MCP client applications.

## What is a Specification?

A specification describes **WHAT** the system does, not **HOW** it is implemented. It defines:

- **Interfaces**: Public APIs, command structures, and data formats
- **Behavior**: How the system responds to inputs and what outputs it produces
- **Requirements**: What must be present, what must be validated, and what must fail
- **Configuration**: What configuration is required and how it is structured
- **Principles**: Design principles and constraints that implementations must follow

**Note**: The configuration file (`{WKS_HOME}/config.json`), MCP commands (`wksm_*`), and CLI commands (`wksc *`) are all part of the public interface and must be fully specified. These are the contracts that users and AI agents interact with, and they must remain stable even if the implementation changes.

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
