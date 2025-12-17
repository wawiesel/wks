# Vault Specification

## Purpose

Central knowledge linker: store edges (links) between resources in the personal knowledge graph.
- **Monitor** = nodes (files being tracked)
- **Vault** = edges (links between files)

## Configuration

- Location: `{WKS_HOME}/config.json` (override via `WKS_HOME`)
- Composition: Uses `vault` block as defined in `docs/specifications/wks.md`; all fields required, no defaults in code.

```json
{
  "vault": {
    "type": "obsidian",
    "base_dir": "~/_vault",
    "database": "vault"
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Vault type (currently only `obsidian`) |
| `base_dir` | string | Path to vault root directory |
| `database` | string | MongoDB collection name |

## Normative Schema

- Canonical output schema: `docs/specifications/vault_output.schema.json`
- Implementations MUST validate outputs against this schema; unknown fields are rejected.

## Database Schema

Collection: `wks.vault`

Each edge is one document. `_id` is `sha256(from_uri + line_number + column_number + to_uri)` for deterministic upserts.

| Field | Type | Description |
|-------|------|-------------|
| `from_uri` | string | URI of source file |
| `line_number` | int | 1-based line number |
| `column_number` | int | 1-based column number |
| `to_uri` | string | URI of target resource |
| `status` | string | `ok`, `missing_symlink`, `missing_target` |

### URI Schemes

- `vault:///path/to/note.md` — Vault-internal notes
- `file:///absolute/path` — External files (via _links/ symlinks on Obsidian)
- `https://...` — External URLs

## Monitor Registration

Vault uses the monitor API to register paths. State is stored in `{WKS_HOME}/vault.json`.

### State File

```json
{
  "base_dir": "~/_vault",
  "registered_include": "~/_vault",
  "registered_exclude": "~/_vault/_links"
}
```

### Registration Flow

On `vault sync` or startup:

1. Load saved state from `{WKS_HOME}/vault.json`
2. Compare `config.vault.base_dir` to saved `base_dir`
3. If changed:
   - Call `wksm_monitor_filter_remove` for old paths
   - Call `wksm_monitor_filter_add` for new paths
   - Update `vault.json`
4. On first run (no state file): register paths and create state file

### Status Validation

`vault status` checks:
- Is vault `base_dir` in monitor's `include_paths`? (warn if not)
- Is vault exclude path in monitor's `exclude_paths`? (warn if not)

Monitor remains agnostic—vault is just directories.

## Link Validation

External file links (`file:///...` URIs) MUST be validated against monitor before being added to the database.

For each external file link discovered during sync:

1. Call `wksm_monitor_check` on the target path
2. If `is_monitored` is `false`: skip, record as issue
3. If `is_monitored` is `true`: add edge to database

`vault status` reports count/list of unmonitored link targets.

## CLI

Entry: `wksc vault`

### status

- Command: `wksc vault status`
- Behavior: Report edge counts, link health, issues, last sync time
- Output schema: `VaultStatusOutput`

### sync

- Command: `wksc vault sync [path]`
- Behavior: Parse file(s) for links, validate external links, upsert valid edges, delete stale edges. Without path: scan entire vault. With path: incremental sync of that file.
- Output schema: `VaultSyncOutput`

### check

- Command: `wksc vault check [path]`
- Behavior: Check link health for file or entire vault
- Output schema: `VaultCheckOutput`

### links

- Command: `wksc vault links <path> [--direction to|from|both]`
- Behavior: Show all edges to/from a specific file
- Output schema: `VaultLinksOutput`

## MCP

Commands mirror CLI:

- `wksm_vault_status`
- `wksm_vault_sync [path]`
- `wksm_vault_check [path]`
- `wksm_vault_links <path> [direction]`

Output format: JSON. CLI and MCP MUST return the same data and structure.

## Daemon Integration

The daemon watches the vault directory and triggers `vault sync` on file changes:

- On markdown file change: calls `wksm_vault_sync <changed_file>`
- Uses daemon's `sync_interval_secs` for debouncing (same as monitor)

## Error Semantics

- Unknown/invalid paths or schema violations return schema-conformant errors; no partial success.
- All outputs MUST validate against their schemas before returning.

## Formal Requirements

- VAU.1 — All vault config fields are required; no defaults in code.
- VAU.2 — `wksc vault status` returns `VaultStatusOutput`.
- VAU.3 — `wksc vault sync [path]` syncs edges; returns `VaultSyncOutput`.
- VAU.4 — `wksc vault check [path]` validates links; returns `VaultCheckOutput`.
- VAU.5 — `wksc vault links <path>` requires path; returns `VaultLinksOutput`.
- VAU.6 — Schema validation required; unknown/invalid inputs yield schema-conformant errors.

## Provider Notes

The `obsidian` vault type:
- Uses `_links/<machine>/` symlink convention for external files
- Creates/updates symlinks during sync for external file links
- Parses Obsidian-style wikilinks and embeds

Future vault types may implement different conventions.
