# Mv Specification

## Purpose
Move files within monitored paths, enforcing naming conventions and updating the database. Provides a safe, controlled mechanism for file relocation that maintains knowledge graph integrity.

## Configuration
- Location: `{WKS_HOME}/config.json`
- Block: `mv`

### Structure
```json
"mv": {
    "always_allow_sources": ["~/Downloads"]
}
```

### Fields
- `always_allow_sources`: List of directories from which moves are always permitted, bypassing source monitor checks. Paths are normalized (~ expanded, made absolute).

## Rules
1. **No overwriting**: Destination must not exist.
2. **Source validation**: Source must exist and be either monitored or in `always_allow_sources`.
3. **Git protection**: Files tracked by version control cannot be moved.
4. **Filename format**: Destination filename must follow `YYYY-Title`, `YYYY_MM-Title`, or `YYYY_MM_DD-Title` format (e.g., `2026-My_Document.pdf`). Title words are underscore-separated, each starting with a capital letter. Filename validation is skipped when the name is unchanged (pure directory move).
5. **Destination monitoring**: Destination parent directory must be monitored.
6. **Database update**: After a successful move, the old record is deleted from the nodes database and the new path is synced.

## CLI

- Entry: `wksc mv`
- Output formats: `--display yaml` (default) or `--display json`

### mv
- Command: `wksc mv <source> <dest>`
- Behavior: Move source file to destination, validating all rules above.
- Output schema: `MvMvOutput` with fields: `errors`, `warnings`, `source`, `destination`, `database_updated`, `success`.

## MCP

| Tool | Description |
|------|-------------|
| `wksm_mv(source, dest)` | Move a file within monitored paths |

- Output format: JSON.
- CLI and MCP MUST return the same data and structure for equivalent calls.

## Error Semantics
- All validation failures return schema-conformant error responses with specific error messages; no partial success.
- All outputs MUST validate against their schemas before returning to CLI or MCP.

## Formal Requirements
- MV.1 — Source must exist; moving a nonexistent file MUST fail.
- MV.2 — Destination must not exist; overwriting MUST fail.
- MV.3 — Git-tracked files MUST NOT be moved.
- MV.4 — Destination filename MUST follow date-title format when renamed.
- MV.5 — Source must be monitored or in `always_allow_sources`; destination parent must be monitored.
- MV.6 — Database is updated after successful move (old record deleted, new path synced).
- MV.7 — CLI/MCP parity: same data and structure for equivalent commands.
