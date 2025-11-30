# Contributing to WKS

## Development Setup

1. **Virtual Environment**: Always use a virtual environment.
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Dependencies**: Install whatever you need in `.venv`.

## Coding Standards

### General Principles
- **DRY (Don't Repeat Yourself)**: Zero code duplication between CLI and MCP.
- **KISS (Keep It Simple, Stupid)**: Eliminate unnecessary features and complexity.
- **No Hedging**: Remove fallback logic. No silent defaults or implicit substitutions. Fail fast and visibly.

### Code Metrics
- **Complexity**: Use `lizard` to measure metrics.
  - **CCN (Cyclomatic Complexity Number)**: Must be ≤ 10 per function.
  - **NLOC (Non-Comment Lines of Code)**: Must be ≤ 100 per function.
- **File Size**: If a file exceeds 900 lines, break it up (includes tests).

### Type Safety & Data Structures
- **Strong Typing**: Favor strong typing over dynamic typing.
- **Dataclasses**: Use `dataclasses` for configuration and data transfer objects. Avoid dictionaries.
- **Validation**: Validate strictly on load (`__post_init__`). Fail immediately if data is invalid.

### Error Handling
- **Structured Aggregation**: Replace ad-hoc error handling with structured aggregation. Collect all errors and raise them together.
- **Deterministic Behavior**: Fail fast and visibly. Avoid optional or hidden recovery logic.
- **Logging**:
  - Use a logger for all info/debug/warning/error conditions.
  - **MCP**: Send warning/errors in the JSON packet.
  - **CLI**: Emit warnings/errors to STDERR. Info/debug goes to logs only.

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
