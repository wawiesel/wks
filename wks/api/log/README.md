# Unified Logging Utilities

This module (`wks.api.log._utils`) provides stateless utilities for appending to and reading from the unified WKS log file.

## Design Principles

*   **Stateless**: Functions do not hold internal state.
*   **Explicit State**: Paths and configurations are passed as arguments (Dependency Injection).
*   **DRY**: Common patterns (like the log line regex) are exposed as constants to avoid duplication.
*   **Simple I/O**: Functions focus on file I/O and parsing, leaving higher-level logic (commands, orchestration) to consumers.

## API

### `LOG_PATTERN`

Regex pattern to parse standard WKS log lines:
`[TIMESTAMP] [DOMAIN] LEVEL: message`

### `append_log(log_path, domain, level, message)`

Appends a log entry with the current UTC timestamp.

### `read_log_entries(log_path, ...retention_days...)`

Reads the log file, filters out entries older than the provided retention periods (Prune-On-Access), and returns lists of warnings and errors. It rewrites the file with only the valid non-expired entries.
