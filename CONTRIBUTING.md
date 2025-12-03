# Contributing to WKS

## Development Setup

1. **Virtual Environment**: Always use a virtual environment.
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Dependencies**: Install whatever you need in `.venv`.

## Git Commit Standards

We follow the **Conventional Commits** specification for clear and machine-readable commit history.

**Format**:
```text
<type>(<scope>): <subject>

<body>

<footer>
```

**Types**:
- `feat`: A new feature
- `fix`: A bug fix
- `docs`: Documentation only changes
- `style`: Changes that do not affect the meaning of the code (white-space, formatting, etc.)
- `refactor`: A code change that neither fixes a bug nor adds a feature
- `perf`: A code change that improves performance
- `test`: Adding missing tests or correcting existing tests
- `chore`: Changes to the build process or auxiliary tools and libraries

**Examples**:
- `feat(auth): implement jwt token validation`
- `fix(cli): resolve crash on missing config file`
- `docs: update contributing guidelines`

## Coding Standards

### General Principles
- **DRY (Don't Repeat Yourself)**: Zero code duplication between CLI and MCP.
- **KISS (Keep It Simple, Stupid)**: Eliminate unnecessary features and complexity.
- **No Hedging**: Remove fallback logic. No silent defaults or implicit substitutions. Fail fast and visibly.
- **No Internal Backwards Compatibility Shims**: Do not add compatibility wrappers or legacy code paths inside this repository to support older call sites (e.g., "compat" helpers that quietly reshape configs or emulate old behavior). Instead, update all callers to the new interfaces and raise clear, actionable errors when inputs are invalid or incomplete.

### Code Metrics
- **Complexity**: Use `lizard` to measure metrics.
  - **CCN (Cyclomatic Complexity Number)**: Must be ≤ 10 per function.
  - **NLOC (Non-Comment Lines of Code)**: Must be ≤ 100 per function.
- **File Size**: If a file exceeds 900 lines, break it up (includes tests).

### Type Safety & Data Structures
- **Strong Typing**: Favor strong typing over dynamic typing.
- **Dataclasses over Dicts**: Use `dataclasses` for all structured data (configuration, DTOs, API responses). Pass dataclasses between layers, not dictionaries. Use `to_dict()` only at serialization boundaries (JSON output, MCP responses).
- **Validation**: Validate strictly on load (`__post_init__`). Fail immediately if data is invalid.

### Error Handling
- **Structured Aggregation**: Replace ad-hoc error handling with structured aggregation. Collect all errors and raise them together.
- **Deterministic Behavior**: Fail fast and visibly. Avoid optional or hidden recovery logic.
- **Logging**:
  - Use a logger for all info/debug/warning/error conditions.
  - **MCP**: Send warning/errors in the JSON packet.
  - **CLI**: Emit warnings/errors to STDERR. Info/debug goes to logs only.

## Architecture & Design Principles

### Layered Architecture

WKS follows a three-layer architecture with clear separation of concerns:

1. **Python API (Core Business Logic)**
   - Controllers, business logic, data structures
   - Beautiful, well-tested code with 100% test coverage
   - No UI concerns, no protocol-specific code
   - Located in `wks/` package modules (e.g., `wks.monitor.controller`, `wks.transform.controller`)
   - Pure Python functions/classes that can be imported and used directly

2. **MCP Server Layer (Thin Protocol Wrapper)**
   - Thin layer on top of the Python API
   - Translates MCP protocol requests to API calls
   - Returns structured results via `MCPResult` (with data, messages, errors)
   - MCP is the **source of truth** for all errors, warnings, and messages
   - Located in `wks/mcp.py` and `wks/mcp/`
   - All MCP tools call the Python API, never duplicate business logic

3. **CLI Layer (Thin User Interface Wrapper)**
   - Thin layer that **only** calls MCP tools
   - Formats MCP results for human-readable output
   - Handles stdin/stdout/stderr according to CLI guidelines
   - Located in `wks/cli/`
   - **All** CLI commands call MCP tools via `call_tool()` - zero business logic in CLI
   - No exceptions: every CLI command is just argument parsing + MCP call + output formatting

**Design Decisions:**
- **MCP as Source of Truth**: CLI calls MCP tools rather than duplicating logic. This ensures consistency and makes MCP the authoritative interface.
- **No Business Logic in CLI**: CLI is strictly argument parsing, MCP tool calls, and output formatting. All business logic is in the Python API, called by MCP.
- **Structured Results**: MCP tools return `MCPResult` objects with structured data, messages, errors, and warnings. CLI consumes and formats these.
- **Zero Duplication**: Business logic exists only in the Python API. MCP and CLI are thin wrappers.
- **Testability**: The Python API can be tested independently of MCP or CLI protocols.
- **Flow**: `CLI → MCP → API` - CLI never calls API directly, MCP never contains business logic

### Error Handling & Logging (Architecture)

**Single Source of Truth**: All errors, warnings, and messages originate in MCP tools (which call the Python API).
- MCP tools return structured `MCPResult` objects with:
  - `success`: bool
  - `data`: dict (actual result data)
  - `messages`: list of structured messages (error, warning, info, status)
  - `log`: optional list of log entries for debugging
- CLI consumes `MCPResult` and formats messages appropriately:
  - Errors/Warnings/Info → STDERR
  - Status messages → STDERR
  - Result data → STDOUT (if success)
- MCP protocol sends warnings/errors in JSON-RPC response packets

### Design Patterns
- **Strategy Pattern**: Use for display modes and engine implementations.
- **Controller Pattern**: Centralize business logic in controllers shared by CLI and MCP.

## CLI Guidelines

Every CLI command must follow this 4-step behavior:
1. **Announce**: Immediately say what you are doing on STDERR.
2. **Progress**: Start a progress bar on STDERR.
3. **Result**: Say what you did and report problems on STDERR.
4. **Output**: Display the final output on STDOUT.
   - Use colorized output (red for failures).
   - Show OK/FAIL status before the last error.
   - If failed, STDOUT should be empty.

## Testing

- **Clean Up**: Remove or disable obsolete tests tied to deprecated functionality.
- **Validation**: Ensure remaining tests pass after refactoring.
