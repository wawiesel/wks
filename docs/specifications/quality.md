# Quality & Standards Specification

## Code Metrics
- **Cyclomatic Complexity (CCN)**: Must be ≤ 10 per function.
- **Lines of Code (NLOC)**: Must be ≤ 100 per function.
- **File Size**: Files > 900 lines must be split.

## Error Handling
- **Structured Aggregation**: Replace ad-hoc error handling with structured aggregation—collect all errors, then raise them together.
- **Fail Fast**: Keep system behavior deterministic. Avoid optional or hidden recovery logic.

## CLI Command Lifecycle
Every CLI command must strictly follow this 4-step behavior:
1.  **Announce**: Immediately output action description to STDERR.
2.  **Progress**: Display a progress bar on STDERR.
3.  **Result**: Report completion status and any issues on STDERR.
4.  **Output**: Display the final structured output on STDOUT (or empty if failure prevents rendering).
