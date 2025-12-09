# Database Specification

## Purpose
Database commands (list/show/reset) with consistent schemas across CLI and MCP.

## Configuration File Structure
- Location: `{WKS_HOME}/config.json` (override with `export WKS_HOME=/custom/path`, default `~/.wks`)
- Composition: Uses the `database` block as defined in `docs/specifications/wks.md`; no defaults in code; missing fields fail validation.

## Normative Schema
- Canonical output schema: `docs/specifications/database_output.schema.json`.
- Implementations MUST validate outputs against this schema; unknown fields are rejected.

## CLI

- Entry: `wksc database`
- Output formats: `--display yaml` (default) or `--display json`

### list
- Command: `wksc database list`
- Behavior: Lists available databases (names without prefix).
- Output schema: `DatabaseListOutput` from `database_output.schema.json`.

### show
- Command: `wksc database show <database> [--query JSON] [--limit N]`
- Behavior: Shows documents from the specified collection with optional filter/limit.
- Output schema: `DatabaseShowOutput` from `database_output.schema.json`.

### reset
- Command: `wksc database reset <database>`
- Behavior: Deletes all documents from the specified collection.
- Output schema: `DatabaseResetOutput` from `database_output.schema.json`.

## MCP
- Commands mirror CLI:
  - `wksm_database_list`
  - `wksm_database_show <database> [query] [limit]`
  - `wksm_database_reset <database>`
- Output format: JSON.
- CLI and MCP MUST return the same data and structure for equivalent calls.

## Error Semantics
- Missing/unknown collection or invalid query MUST produce schema-conformant errors; no partial success.
- All outputs MUST validate against their schemas before returning to CLI or MCP.

## Formal Requirements
- DB.1 — Config values are required; no defaults in code; missing fields fail validation.
- DB.2 — `wksc database list` lists all databases (names without prefix).
- DB.3 — `wksc database show <database>` requires a database name; optional query/limit parameters; returns matching documents.
- DB.4 — `wksc database reset <database>` clears the specified database.
- DB.5 — Unknown/invalid database or schema violation returns schema-conformant errors; no partial success.

