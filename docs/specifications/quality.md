# Quality & Standards Specification

**Note**: This specification needs to be updated to align with the principles established in the monitor and database specifications. It should follow the config-first approach (configuration discussed early, database schema discussed later), remove implementation details, and focus on WHAT (interface, behavior, requirements) rather than HOW (implementation details).

## Code Metrics
- **Cyclomatic Complexity (CCN)**: Must be ≤ 10 per function.
- **Lines of Code (NLOC)**: Must be ≤ 100 per function.
- **File Size**: Files > 900 lines must be split.

## Error Handling
- **Structured Aggregation**: Replace ad-hoc error handling with structured aggregation—collect all errors, then raise them together.
- **Fail Fast**: Keep system behavior deterministic. Avoid optional or hidden recovery logic.

## Command Execution Pattern (CLI & MCP)
Every command (CLI or MCP) must strictly follow this 4-step behavior:
1.  **Announce**: Immediately output action description (CLI: STDERR, MCP: status message).
2.  **Progress**: Display a progress indicator with time estimate (CLI: progress bar on STDERR, MCP: progress notifications).
3.  **Result**: Report completion status and any issues (CLI: STDERR, MCP: result notification messages).
4.  **Output**: Display the final structured output (CLI: STDOUT, MCP: result notification data, or empty if failure prevents rendering).
