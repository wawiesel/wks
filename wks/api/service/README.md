# Service API

The service package abstracts platform-specific daemon installation and control.

## Rules

- Platform backends stay behind the shared abstraction.
- CLI and MCP use the same service command wrappers.
