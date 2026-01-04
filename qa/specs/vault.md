# Vault Specification

## Purpose

The **Vault** is a knowledge base (currently Obsidian-compatible) that provides:

1. **Configuration**: Defines the vault root directory and backend type.
2. **Monitor Registration**: Automatically registers the vault with the Monitor domain.
3. **URI Scheme**: Uses `vault:///relative/path` for portable in-vault references.
4. **Scoped Operations**: Provides vault-specific `status` and `sync` commands.

For **edge storage and management**, see [Link Specification](link.md).

## Configuration

Location: `{WKS_HOME}/config.json`

```json
{
  "vault": {
    "type": "obsidian",
    "base_dir": "~/_vault"
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Vault backend type (currently only `obsidian`) |
| `base_dir` | string | Path to vault root directory |

All fields are required; no defaults in code.

## URI Scheme

Files within the vault use the `vault:///` scheme for portability:

| Location | URI Format | Example |
|----------|------------|---------|
| In-Vault | `vault:///<relative_path>` | `vault:///Concepts/Agent.md` |
| External | `file://<hostname>/<absolute_path>` | `file://laptop/Users/me/doc.md` |

This allows the vault to be moved or synced across machines without breaking internal links.

> [!IMPORTANT]
> The vault should only have **outgoing** links. No edges should have `to_uri` starting with `vault:///` from non-vault sources.

## Path Resolution

All `wksc vault` commands interpret paths as **vault-relative**:

**If CWD is inside vault** (e.g., `~/_vault/Projects`):
- `Index.md` → `vault:///Projects/Index.md` (relative to CWD)

**If CWD is outside vault** (e.g., `~/Desktop`):
- `Index.md` → `vault:///Index.md` (relative to vault root)

| Input | CWD | Interpreted As |
|-------|-----|----------------|
| `Index.md` | `~/_vault/Projects` | `vault:///Projects/Index.md` |
| `Index.md` | `~/Desktop` | `vault:///Index.md` |
| `./local/x.md` | `~/Desktop` | `vault:///local/x.md` |
| `vault:///Index.md` | any | `vault:///Index.md` |
| `~/_vault/Index.md` | any | `vault:///Index.md` |

**Error Cases:**
- Path outside vault: `"~/other/file.md" is not in the vault`
- Vault path doesn't exist: `"vault:///local/path/to/x.md" does not exist`

## Monitor Registration

The vault directory is automatically registered with the Monitor domain.

### State File

Location: `{WKS_HOME}/vault.json`

```json
{
  "base_dir": "~/_vault",
  "registered_include": "~/_vault",
  "registered_exclude": "~/_vault/_links"
}
```

### Registration Flow

On daemon startup or config change:

1. Load saved state from `vault.json`
2. Compare `config.vault.base_dir` to saved `base_dir`
3. If changed:
   - Remove old paths from monitor
   - Add new paths to monitor
   - Update `vault.json`

## CLI: `wksc vault`

### status

**Signature**: `wksc vault status`

**Purpose**: Vault-scoped statistics and validation.

- Queries edges where `from_uri` starts with `vault:///`
- Reports node count, edge count for vault only
- **Validates** no invalid incoming edges (edges with `to_uri` starting with `vault:///` from non-vault sources)
- Reports health issues (broken links, missing targets)

### sync

**Signature**: `wksc vault sync [path] [--recursive]`

**Purpose**: Sync vault links with vault-specific processing.

- If `path` is omitted: syncs entire vault (recursive).
- If `path` is a file: syncs that file.
- If `path` is a directory and `--recursive`: syncs all matching files recursively.
- Calls `wksc link sync` to parse and store edges.
- Vault backend may perform backend-specific operations.
- Reports vault-specific sync metrics.

### links

**Signature**: `wksc vault links <path> [--direction to|from|both]`

**Purpose**: Query edges for a file in the vault.

- Shows edges connected to/from the given vault file.
- Default direction: `both`.
- This is a convenience wrapper around `wksc link show` with vault path resolution.

### check

**Signature**: `wksc vault check [path]`

**Purpose**: Check validation of wiki links within the vault.

- Scans a specific file or the entire vault for broken links or errors.
- Reports detailed issues with line numbers and error types.

### Other Link Operations

For general link operations, use `wksc link`:

| Action | Command |
|--------|---------|
| Check links in a file | `wksc link check <path>` |
| Show links for a URI | `wksc link show <uri>` |
| Clean stale links | `wksc link clean` |

## MCP Interface

| Tool | Description |
|------|-------------|
| `wksm_vault_status()` | Get vault-scoped statistics |
| `wksm_vault_sync(path?)` | Sync vault links |
| `wksm_vault_check(path?)` | Check vault link health |
| `wksm_vault_links(path, direction?)` | Query edges for vault file |

For other link operations, use `wksm_link_*` tools.

## Daemon Integration

The daemon watches monitored directories and routes file changes appropriately:

| File Location | Action |
|---------------|--------|
| Within `vault.base_dir` | Calls `wksm_vault_sync(<changed_file>)` |
| Other monitored file | Calls `wksm_link_sync(<changed_file>)` |

Debounced by `sync_interval_secs`.

## Backend: Obsidian

The `obsidian` vault backend:

- Parses WikiLinks: `[[Note]]`, `[[Note|Alias]]`, `![[Embed]]`
- Parses standard Markdown links: `[Text](url)`
- Uses `_links/<machine>/` symlink convention for external file references
- Excludes `_links/` from monitoring to avoid symlink loops

Future vault backends may implement different conventions.

## Formal Requirements

- **VAU.1**: All vault config fields are required; no defaults in code.
- **VAU.2**: `vault status` returns vault-scoped statistics only.
- **VAU.3**: `vault sync` delegates to `link sync` then runs backend-specific ops.
- **VAU.4**: `vault:///` URIs are relative to vault root; portable across machines.
- **VAU.5**: Vault should only have outgoing edges; incoming edges are invalid.
- **VAU.6**: Daemon routes vault files to `vault sync`, others to `link sync`.
- **VAU.7**: `vault check` validates internal validity of vault links.
