# Database

The database layer owns persistence for monitored files, transformed content metadata, vault edges, and search indexes.

## Rules

- Database names follow `<prefix>.<collection>`.
- Backends are selected explicitly through config.
- Missing backends or invalid backend data fail immediately.
- Public commands return consistent structures across CLI and MCP.

## Responsibilities

- CRUD access for collection-oriented command flows
- Backend abstraction for `mongo` and `mongomock`
- Shared use by monitor, vault, transform, index, and search features

## Contract

- Transport layers do not contain backend logic.
- Database configuration stays typed and validated.
- Output models are defined in Python alongside the database command modules.
