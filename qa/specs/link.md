# Link Specification

## Purpose

The **Link** domain is the system's centralized **Edge Provider**. It extracts, stores, and manages relationships (edges) between resources (nodes).

- **Monitor Domain**: Acts as the **Node Index**. It validates which files exist and are "in-scope" (monitored).

This separation of concerns allows the Link domain to operate on any valid node provided by the Monitor, regardless of the underlying content type (e.g., Markdown, HTML, RST), provided a parser exists.

## Database Schema
See `qa/specs/database_edges.md`.

## URI Standard

| Scheme | Format | Example |
|--------|--------|---------|
| Local (External) | `file://<hostname>/<absolute_path>` | `file://laptop/Users/me/doc.md` |
| Vault (Portable) | `vault:///<relative_path>` | `vault:///Concepts/Agent.md` |
| Web | `https://...` | `https://example.com/page` |

## Link Parsers

Link parsers are registered in `wks/api/link/parsers/`. Selection is automatic by file extension or explicit via `--parser`.

| Parser | Extensions | Link Types |
|--------|------------|------------|
| `markdown` | `.md` | WikiLinks `[[...]]`, URLs `[text](url)`, Embeds `![[...]]` |
| `html` | `.html`, `.htm` | `<a href>`, `src` attributes |
| `rst` | `.rst` | `` `text <url>`_ ``, `.. image::` |
| `raw` | `.txt`, fallback | HTTP/HTTPS URLs |

## CLI: `wksc link`

### check

**Signature**: `wksc link check <path> [--parser <name>]`

**Purpose**: Validation and Inspection (Read-Only).

- Verifies if `<path>` is monitored.
- Scans the file for links using the appropriate parser.
- Prints found links with resolved URIs.
- Does **not** write to the database.

### sync

**Signature**: `wksc link sync <path> [--parser <name>] [--recursive] [--remote]`

**Purpose**: State Synchronization (Write).

- If `<path>` is a file: syncs that file.
- If `<path>` is a directory and `--recursive`: syncs all matching files recursively.
- Verifies each file is monitored.
- Scans files for links using the appropriate parser.
- **Writes** edges to `link` collection (replace strategy: delete old, insert new).
- If `--remote` is specified, validates remote URLs exist.

### status

**Signature**: `wksc link status`

**Purpose**: System Health.

- Reports total node count (unique URIs).
- Reports total edge count.

### show

**Signature**: `wksc link show <uri> [--direction to|from|both]`

**Purpose**: Graph Query.

- Lists edges connected to/from the given URI.
- Default direction: `from`.



## MCP Interface

| Tool | Description |
|------|-------------|
| `wksm_link_check(path, parser?)` | Check links in file |
| `wksm_link_sync(path, parser?, remote?)` | Sync links to database |
| `wksm_link_status()` | Get node/edge counts |
| `wksm_link_show(uri, direction?)` | Query edges for URI |
| `wksm_link_clean(remote?)` | Remove stale edges |

## Formal Requirements

- **LNK.1**: All link commands require the file to be monitored (except `status`, `clean`).
- **LNK.2**: `check` is read-only; `sync` writes to database.
- **LNK.3**: Edges use deterministic `_id` for idempotent upserts.
- **LNK.4**: Parsers are selected by extension or explicit `--parser` flag.
- **LNK.5**: `vault:///` URIs are used for files within the vault; `file://` for external.
- **LNK.6**: `sync` uses replace strategy: deletes all edges from source, inserts new.
- **LNK.7**: Path expansion uses shared `wks.api.config.expand_paths()` utility.
