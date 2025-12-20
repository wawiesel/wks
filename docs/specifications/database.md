# Database Specification

## Purpose
Database commands (list/show/reset) with consistent schemas across CLI and MCP.

## Configuration
- Location: `{WKS_HOME}/config.json` (override with `WKS_HOME`)
- Block: `database` (required; missing fields fail validation; no defaults)
- Fields:
  - `type`: `"mongo"` or `"mongomock"`
  - `prefix`: string (collection prefix)
  - `data`: backend-specific object
    - For `type: "mongo"`:
      - `uri`: required MongoDB URI (must be reachable)
      - `local`: boolean flag; if true, the URI must point to the local host/port for a locally started mongod. No additional defaults implied.
    - For `type: "mongomock"`:
      - `data`: `{}` (ignored)

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
    - If `database` is `all`, resets all collections in the configured database (dangerous!).
- Output schema: `DatabaseResetOutput` from `database_output.schema.json`.

### prune
- Command: `wksc database prune <database> [--remote]`
- Behavior: Prunes stale data from the specified database.
    - **Local Pruning** (Default):
        - `nodes`: Removes documents where `local_uri` points to a non-existent file on the filesystem.
        - `edges`: Removes edges where `from_local_uri` (source) points to a node not present in the `nodes` database (orphaned links).
    - **Remote Pruning** (`--remote`):
        - `edges`: Validates `to_remote_uri` targets (HTTP HEAD/GET). Removes edges where the remote resource is unreachable (e.g., 404).
        - *Note*: Remote pruning is additive; local pruning always runs.
    - If `database` is `all`, runs prune on all databases.
- Output schema: `DatabasePruneOutput` from `database_output.schema.json`.

### wksm_database_prune
- Description: Prune stale entries from a database.
- Arguments:
    - `database`: Database to prune ('all', 'nodes', 'edges').
    - `remote`: Boolean (default false) to check remote targets.
- Output schema: `DatabasePruneOutput`.

## MCP

- Commands mirror CLI:
  - `wksm_database_list`
  - `wksm_database_show <database> [query] [limit]`
  - `wksm_database_reset <database>`
  - `wksm_database_prune <database>`
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
- DB.5 — `wksc database prune <database>` removes entries where the local source file (`from_local_uri`) no longer exists.
- DB.6 — Unknown/invalid database or schema violation returns schema-conformant errors; no partial success.
