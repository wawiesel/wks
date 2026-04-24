# Monitor

The monitor tracks files that match the configured include/exclude rules and stores node metadata in the database.

## Responsibilities

- Decide whether a path is monitored
- Calculate priority deterministically
- Sync files and directories into the nodes collection
- Enforce document limits and remove stale records

## Rules

- Include/exclude logic is config-driven.
- Priority calculation is deterministic and testable.
- Missing files are removed from the database when sync confirms they are gone.
- CLI and MCP expose the same monitor command behavior.
