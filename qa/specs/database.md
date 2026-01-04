# Database Specification

## Purpose
Database commands (list/show/reset) with consistent schemas across CLI and MCP.

## Configuration
- Location: `{WKS_HOME}/config.json` (override with `WKS_HOME`)
- Block: `database` (required; missing fields fail validation; no defaults)
- Fields:
  - `type`: `"mongo"` or `"mongomock"`
  - `prefix`: string (collection prefix)
  - `prune_frequency_secs`: number (seconds between automatic prune runs during daemon sync; 0 disables auto-prune)
  - `data`: backend-specific object
    - For `type: "mongo"`:
      - `uri`: required MongoDB URI (must be reachable)
      - `local`: boolean flag; if true, the URI must point to the local host/port for a locally started mongod. No additional defaults implied.
    - For `type: "mongomock"`:
      - `data`: `{}` (ignored)

## Normative Schema
- Canonical output schema: `qa/specs/database_output.schema.json`.
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
        - `edges`:
            - Removes edges where `from_local_uri` (source) points to a node not present in the `nodes` database.
            - Removes edges where `to_local_uri` is populated AND `to_remote_uri` is **NOT populated** AND `to_local_uri` is NEITHER in the `nodes` database NOR exists on the filesystem (broken local-only link).
        - `transform`: Bidirectional sync between database and cache files (see Transform Specification).
    - **Remote Pruning** (`--remote`):
        - `edges`:
            - Requires active internet connection. If offline, remote pruning is skipped.
            - Validates `to_remote_uri` if `to_local_uri` is **NOT populated** OR **broken** (not in DB/FS).
            - Validates `from_remote_uri` (always, if present).
            - If `to_remote_uri` or `from_remote_uri` is unreachable (e.g., 404/410), the respective field is **unset**.
            - This runs **before** limiting local pruning.
        - *Note*: Remote pruning is additive; local pruning always runs.
    - If `database` is `all`, runs prune on all databases.
- Output schema: `DatabasePruneOutput` from `database_output.schema.json`.

### Prune Timer Semantics

The `prune_frequency_secs` configuration controls automatic pruning during daemon sync cycles:

1. **Manual prune** (`wksc database prune`):
   - Runs immediately.
   - Resets the prune timer for that database to zero.

2. **Automatic prune** (daemon sync cycle):
   - Each database maintains its own prune timer (seconds since last prune).
   - During each daemon sync, the timer is checked against `prune_frequency_secs`.
   - If elapsed time ≥ `prune_frequency_secs`, prune runs and timer resets.
   - If `prune_frequency_secs` is 0, automatic pruning is disabled.

3. **Timer persistence**:
   - Prune timers are maintained in the status file (`{WKS_HOME}/database.json`).
   - Maps database name → last prune timestamp.
   - Survives daemon restarts.

## MCP

- Commands mirror CLI:
  - `wksm_database_list`
  - `wksm_database_show <database> [query] [limit]`
  - `wksm_database_reset <database>`
  - `wksm_database_prune <database> [remote]`
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

## Clarifications

### Edge Pruning Scenarios

Assumption: `from_local_uri` (source) is **Valid** (exists in `nodes` DB). If invalid, edge is **always deleted**.
`--remote` flag is ON and internet is available.

#### Target Resolution

| `to_local_uri`                   | `to_remote_uri` | Remote HTTP | Outcome         |
| :------------------------------- | :-------------- | :---------- | :-------------- |
| In `nodes` DB                    | *any*           | *skipped*   | **Keep**        |
| Not in DB, exists on filesystem  | *any*           | *skipped*   | **Keep**        |
| Not in DB, not on filesystem     | Empty/None      | *N/A*       | **Delete**      |
| Not in DB, not on filesystem     | Populated       | 200         | **Keep**        |
| Not in DB, not on filesystem     | Populated       | 404/410     | **Delete**      |
| Not in DB, not on filesystem     | Populated       | Error       | **Keep**        |
| Empty/None                       | Empty/None      | *N/A*       | **Delete**      |
| Empty/None                       | Populated       | 200         | **Keep**        |
| Empty/None                       | Populated       | 404/410     | **Delete**      |
| Empty/None                       | Populated       | Error       | **Keep**        |

#### Source Remote (`from_remote_uri`)

| `from_remote_uri` | Remote HTTP | Action                      |
| :---------------- | :---------- | :-------------------------- |
| Populated         | 200         | Keep field                  |
| Populated         | 404/410     | **Unset field** (no delete) |
| Populated         | Error       | Keep field                  |

*Notes:*
- If `--remote` is **OFF** or offline, remote checks are skipped. Edges with broken local targets but populated `to_remote_uri` are **kept**.
- "Delete" for (Broken Local + 404 Remote) occurs because `to_remote_uri` is unset first, then the edge has no valid targets.
- "Keep on Error" is a safety measure: transient network issues (timeouts, DNS failures, temporary outages) don't confirm the resource is gone. We only delete on **definitive** 404/410 responses.
