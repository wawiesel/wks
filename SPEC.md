# WKS Command-Line Utility (wks0)

This spec documents the wks0 CLI: a layered architecture for filesystem monitoring, knowledge graph management, and semantic indexing.

## Architecture Overview

WKS is built as a stack of independent, composable layers:

```
                    ┌──────────────────────────────────────────┐
                    │  Patterns Layer                          │
                    │  AI agents executing organizational      │
                    │  patterns for knowledge management       │
                    └──────────────────────────────────────────┘
                                      ↓
                    ┌──────────────────────────────────────────┐
                    │  Search Layer                            │
                    │  Semantic + keyword search combining     │
                    │  multiple indices with weighted results  │
                    └──────────────────────────────────────────┘
                                      ↓
                    ┌──────────────────────────────────────────┐
                    │  Diff Layer                              │
                    │  Pluggable comparison engines            │
                    │  (myers, bsdiff3, ...)                   │
                    └──────────────────────────────────────────┘
                                      ↓
                    ┌──────────────────────────────────────────┐
                    │  Transform Layer                         │
                    │  Multi-engine document conversion        │
                    │  Docling (PDF/DOCX/PPTX → Markdown)      │
                    │  Extensible converter plugin system      │
                    └──────────────────────────────────────────┘
                                      ↓
                    ┌──────────────────────────────────────────┐
                    │  Vault Layer                             │
                    │  Knowledge graph link tracking           │
                    │  Obsidian + extensible vault types       │
                    │  Symlinks: _links/<machine>/             │
                    └──────────────────────────────────────────┘
                                      ↓
                    ┌──────────────────────────────────────────┐
                    │  Monitor Layer                           │
                    │  Filesystem tracking + priority scoring  │
                    │  Paths, checksums, modification times    │
                    └──────────────────────────────────────────┘
```

**Design Principles**:
- **Config-First**: All defaults defined in `~/.wks/config.json`
- **Override Anywhere**: CLI and MCP can override any config parameter
- **Engine Plugins**: Each layer supports multiple engines with dedicated configuration
- **Zero Duplication**: CLI and MCP share identical business logic via controllers

## Installation
- Recommended: `pipx install .`
- Optional: `pipx runpip wks0 install docling` (for PDF/Office transformation)
- Python: 3.10+

## Configuration

Stored at `~/.wks/config.json`

```json
{
  "monitor": {
    "include_paths": ["~"],
    "exclude_paths": ["~/Library", "~/_vault", "~/.wks", "~/miniforge3"],
    "include_dirnames": [],
    "exclude_dirnames": [
      ".cache", ".venv", "__pycache__", "_build",
      "build", "dist", "node_modules", "venv"
    ],
    "include_globs": [],
    "exclude_globs": [
      "**/.DS_Store", "*.swp", "*.tmp", "*~", "._*", "~$*", ".~lock.*#"
    ],
    "managed_directories": {
      "~/Desktop": 150,
      "~/deadlines": 120,
      "~": 100,
      "~/Documents": 100,
      "~/Pictures": 80,
      "~/Downloads": 50
    },
    "priority": {
      "depth_multiplier": 0.9,
      "underscore_divisor": 2,
      "single_underscore_divisor": 64,
      "extension_weights": {
        ".docx": 1.3,
        ".pptx": 1.3,
        ".pdf": 1.1,
        "default": 1.0
      }
    },
    "database": "wks.monitor",
    "log_file": "~/.wks/monitor.log"
  },

  "vault": {
    "type": "obsidian",
    "base_dir": "~/_vault",
    "wks_dir": "WKS",
    "update_frequency_seconds": 10,
    "database": "wks.vault"
  },

  "db": {
    "type": "mongodb",
    "uri": "mongodb://localhost:27017/"
  },

  "transform": {
    "cache": {
      "max_size_bytes": 1073741824,
      "location": ".wks/transform/cache"
    },
    "engines": {
      "docling": {
        "enabled": true,
        "ocr": false,
        "timeout_secs": 30,
        "max_chars": -1,
        "write_extension": "md"
      }
    }
  },

  "diff": {
    "engines": {
      "bsdiff3": {
        "enabled": true
      },
      "myers": {
        "enabled": true,
        "context_lines": 3
      }
    }
  },

  "index": {
    "indices": {
      "main": {
        "enabled": true,
        "type": "embedding",
        "include_extensions": [
          ".md", ".txt", ".py", ".ipynb", ".tex",
          ".docx", ".pptx", ".pdf", ".html",
          ".csv", ".xlsx"
        ],
        "respect_monitor_ignores": false,
        "respect_priority": true,
        "database": "wks_index_main",
        "collection": "documents"
      },
      "code": {
        "enabled": false,
        "type": "ast",
        "include_extensions": [".py", ".js", ".ts", ".cpp"],
        "database": "wks_index_code",
        "collection": "code_blocks"
      }
    }
  },

  "search": {
    "default_index": "main",
    "combine": {
      "enabled": false,
      "indices": ["main", "code"],
      "weights": {
        "main": 0.7,
        "code": 0.3
      }
    }
  },

  "display": {
    "timestamp_format": "%Y-%m-%d %H:%M:%S"
  }
}
```

## Layer Descriptions

### Monitor Layer

**Purpose**: Track filesystem state and calculate priorities

**Database**: `wks.monitor`

**Schema**:
- `path` — absolute URI (e.g., `file:///Users/ww5/Documents/report.pdf`)
- `timestamp` — ISO 8601 UTC string for last modification
- `checksum` — SHA256 hash of file contents
- `bytes` — file size in bytes
- `priority` — calculated integer score (1-∞) based on path structure

**Priority Calculation**:
1. Match file to deepest `managed_directories` entry (e.g., `~/Documents` → 100)
2. For each path component after base: multiply by `depth_multiplier` (0.9)
3. For each leading `_` in component name: divide by `underscore_divisor` (2)
4. If component is single `_`: divide by `single_underscore_divisor` (64)
5. Multiply by extension weight from `extension_weights`
6. Round to integer (minimum 1)

**Example**: `/Users/ww5/Documents/reports/_old/draft.pdf`
- Matches: `~/Documents` (base = 100)
- `reports`: 100 × 0.9 = 90
- `_old`: 90 × 0.9 × 0.5 = 40.5
- Extension `.pdf`: 40.5 × 1.1 = 44.55
- **Priority: 45**

**Monitor include/exclude logic**:
- `include_paths` and `exclude_paths` store canonical directories (fully-resolved on load). A path must appear in exactly one list; identical entries across both lists are a validation error. When evaluating a file/directory, resolve it and walk its ancestors until one appears in either list. The nearest match wins. If the closest ancestor is in `exclude_paths` (or no ancestor is found at all), the path is excluded immediately and no further checks run.
- Once a path survives the root check, the daemon applies directory/glob rules in two phases:
  - **Exclusion phase**: evaluate `exclude_dirnames` (the immediate parent directory) and `exclude_globs` (full path/basename). If either matches, the path becomes “tentatively excluded”.
  - **Inclusion overrides**: evaluate `include_dirnames` and `include_globs`. If a path was tentatively excluded but matches an include rule, the exclusion is reversed and the path is monitored. If neither include rule fires, the exclusion stands. Dirname/glob lists must not share entries; duplicates are validation errors, and entries that duplicate the opposite glob list are flagged as redundant.

**Commands**:
- `wks0 monitor status` — show monitoring statistics (supports `--live` for auto-updating display)
- `wks0 monitor include_paths add <path>` — add path to include_paths
- `wks0 monitor exclude_paths add <path>` — add path to exclude_paths
- `wks0 monitor ignore_dirnames add <name>` — add directory name(s) that should always be ignored
- `wks0 monitor ignore_globs add <pattern>` — add glob(s) that should always be ignored
- `wks0 db monitor` — query filesystem database

### Vault Layer

**Goal**: Keep vault markdown, `_links/` symlinks, and filesystem state aligned without manual intervention. The vault database is the bridge between the scanner and the monitor—no human-facing "fix it" commands exist.

**Database**: `wks.vault`

**URI-First Design**: All links stored as cross-platform URIs. Local filesystem paths derived on-demand from URIs.

#### Symlink Naming Convention

External files are mirrored under `_links/<machine>/` to match filesystem structure:
```
_links/
  mbp-2021/
    Users/ww5/Documents/papers/paper.pdf → /Users/ww5/Documents/papers/paper.pdf
    Users/ww5/2025-ProjectName/README.md → /Users/ww5/2025-ProjectName/README.md
```

**Benefits**:
- Multi-machine vault sync (each machine has its own `_links/<machine>/` tree)
- Mirrors actual filesystem for predictable paths
- Enables automatic symlink management via monitor events

#### Schema

Each link becomes exactly one document. `_id` is `sha256(from + line_number + to_uri)` so repeated scans upsert deterministically. Fields are grouped as follows:

1. **Source context**
   - `from`: note path relative to vault root (e.g., `Projects/Foo.md`)
   - `from_uri`: cross-platform URI to source note (e.g., `vault:///Projects/Foo.md`)
   - `line_number`: 1-based line that produced the link
   - `source_heading`: nearest markdown heading text (empty string if none)
   - `raw_line`: full line content trimmed to a safe length for debugging

2. **Link content**
   - `link_type`: `wikilink`, `embed`, or `markdown_url`
   - `raw_target`: text inside the link (`[[…]]` target or `(…)` URL), including alias
   - `alias_or_text`: alias or `[text]` label (empty string when not supplied)

3. **Target resolution (URI-first)**
   - `to`: target path relative to vault root (e.g., `_links/mbp-2021/Users/ww5/papers/paper.pdf`)
   - `to_uri`: cross-platform URI to target resource
     - Vault notes: `vault:///Projects/Demo.md`
     - _links/ symlinks (resolved): `file:///Users/ww5/papers/paper.pdf`
     - External URLs: `https://example.com`
     - Attachments: `vault:///_attachments/image.png`

4. **Health & lifecycle**
   - `status`: `ok`, `missing_symlink`, `missing_target`, or `legacy_link`
   - `first_seen`: ISO timestamp from the initial scan that created the document
   - `last_seen`: ISO timestamp from the latest scan that observed the link
   - `last_updated`: ISO timestamp of the most recent write (scan or monitor-triggered)

**Removed Fields** (derivable from other fields):
- `is_embed` — derive from `link_type == "embed"`
- `target_kind` — derive from `to` pattern (starts with `_links/`, `_attachments/`, etc.)
- `links_rel` — redundant with `to` for _links/ symlinks
- `resolved_path` — derive from `to_uri` when needed via `urllib.parse.urlparse(to_uri).path`
- `resolved_exists` — check on-demand, don't cache stale boolean
- `monitor_doc_id` — query monitor DB when needed via `to_uri`

A single metadata document (`_id = "__meta__"`, `doc_type = "meta"`) stores `last_scan_started_at`, `last_scan_duration_ms`, `notes_scanned`, `edges_written`, per-status counts, per-type counts, and the array `errors`. Status commands read this row instead of recomputing aggregates.

#### URI Conversion

**Derive filesystem paths when needed**:
```python
from pathlib import Path
from urllib.parse import urlparse

def uri_to_path(uri: str, vault_root: Path) -> Path:
    if uri.startswith("file://"):
        return Path(urlparse(uri).path)
    elif uri.startswith("vault://"):
        rel = uri.removeprefix("vault:///")
        return vault_root / rel
    else:
        raise ValueError(f"Cannot convert {uri} to filesystem path")
```

#### Order of Operations

**Core Principle**: The vault database is the source of truth for link management. We only create/update/delete symlinks in `_links/` when the vault DB shows that vault notes reference those files. The monitor tracks all files in managed directories, but vault operations are **only triggered when the vault DB indicates a reference exists**.

##### Scenario 1: New File in Managed Directory

When a new file appears in a monitored directory (e.g., `~/2025-ProjectName/new_file.md`):

1. **Monitor Detects Creation** — watchdog event → daemon callback
2. **Coalesce Period** — file sits in `_pending_mods` for ~2 seconds
3. **Flush to Monitor DB** — after coalesce, logged and stored in `wks.monitor`
4. **No Vault Action** — **Critical:** No symlink created, no vault operations occur
5. **Wait for Reference** — Only if user later adds `[[_links/...]]` in vault will symlink be created

**Key Insight**: Monitoring ≠ Linking. Monitor tracks ALL files. Vault only acts on referenced files.

##### Scenario 2: New Link in Vault

When user adds a link in vault markdown (file:// URL, absolute path, or wikilink):

**For file:// URLs or absolute paths**:

1. **User Edits Note** — adds `[doc](file:///Users/ww5/report.pdf)` or `[[/absolute/path]]`
2. **Git Detects Change** — vault note marked as modified
3. **Periodic Vault Sync** — daemon runs `indexer.sync(incremental=True)` every ~5 minutes
4. **Incremental Scan** — scanner processes only git-modified files
5. **File URL Conversion** — if file:// URL found and target exists:
   - Create symlink at `_links/<machine>/path/to/file`
   - Record rewrite: `(note, line, old_url, new_wikilink)`
6. **Link Record Created** — `VaultEdgeRecord` with status (ok/missing_symlink/missing_target)
7. **Vault DB Updated** — batch upsert to `wks.vault` collection
8. **Markdown Rewriting** — replace `file:///...` with `[[_links/...]]` in vault note
9. **Symlink Active** — Obsidian can now preview/open the file

**For direct wikilinks** (`[[_links/...]]`):
- Same flow, but skips conversion
- If symlink missing: status = `missing_symlink`
- Run `wks vault fix-symlinks` to create

**Key Insight**: Vault scan drives symlink creation. Scanner creates symlinks, records links in DB, and rewrites markdown for consistency.

##### Scenario 3: Referenced File is Moved

When a file that vault notes reference is moved:

1. **Monitor Detects Move** — watchdog event `(src, dest)`
2. **Update Symlink** — old `_links/.../old/path` deleted, new `_links/.../new/path` created
3. **Update Vault DB** — all records where `to_uri = old_uri` updated to `to_uri = new_uri`
4. **Rewrite Wikilinks** — scan vault notes, replace `[[_links/.../old/path]]` → `[[_links/.../new/path]]`
5. **Update Monitor DB** — remove old path, add new path
6. **No Deletion Marker** — `has_references_to(old_path)` returns false after updates

**Atomic update across 4 layers**:
- Symlinks: `_links/` points to new location
- Vault DB: `to_uri` fields updated
- Vault notes: wikilinks rewritten
- Monitor DB: path tracking updated

**Key Insight**: Move operations cascade through all layers to maintain consistency. No broken references after move.

**Derive target_kind when needed**:
```python
def derive_target_kind(to: str, to_uri: str) -> str:
    if to.startswith("_links/"):
        return "_links_symlink"
    elif to.startswith("_") and not to.startswith("_links/"):
        return "attachment"
    elif not to_uri.startswith("vault://"):
        return "external_url"
    elif to.startswith("links/") or to.startswith("/"):
        return "legacy_path"
    else:
        return "vault_note"
```

#### Automation Workflow

**Monitor-Vault Integration** (event-driven):

When filesystem monitor detects a file move:
```python
def on_file_moved(event):
    old_path = event.src_path  # /Users/ww5/papers/paper.pdf
    new_path = event.dest_path  # /Users/ww5/archive/paper.pdf

    old_uri = Path(old_path).as_uri()  # file:///Users/ww5/papers/paper.pdf
    new_uri = Path(new_path).as_uri()  # file:///Users/ww5/archive/paper.pdf
    machine = get_machine_name()  # "mbp-2021"

    # Update monitor DB
    monitor_db.update_one(
        {"path": old_uri},
        {"$set": {"path": new_uri, ...}}
    )

    # Update vault DB (all links pointing to this file)
    vault_db.update_many(
        {"to_uri": old_uri},
        {"$set": {
            "to_uri": new_uri,
            "to": f"_links/{machine}/{new_path}",
            "status": "ok",
            "last_updated": now_iso()
        }}
    )

    # Move symlink to mirror new location
    old_symlink = vault_root / "_links" / machine / old_path.strip("/")
    new_symlink = vault_root / "_links" / machine / new_path.strip("/")
    move_symlink(old_symlink, new_symlink, target=new_path)

    # Update markdown files
    for affected_note in vault_db.find({"to_uri": new_uri}):
        update_markdown_link(
            note_path=affected_note["from"],
            line_number=affected_note["line_number"],
            old_target=f"_links/{machine}/{old_path}",
            new_target=f"_links/{machine}/{new_path}"
        )
```

**Scanner Loop**:
1. Runs every `vault.update_frequency_seconds` (default: 10)
2. Scans all `.md` files in vault
3. Parses wikilinks `[[...]]`, embeds `![[...]]`, markdown URLs `[]()`
4. Resolves _links/ symlinks to get `file://` URIs
5. Generates `from_uri` (vault:// for source) and `to_uri` (vault:// or file:// for target)
6. Upserts link documents (deterministic `_id` from from + line_number + to_uri)
7. Deletes stale links (not seen in current scan)
8. Updates `__meta__` document with scan statistics

**Status Reporting**: Reads persisted counts from `__meta__` and queries unhealthy edges by `status != "ok"`.

**Commands** (diagnostics only):
- `wks0 vault status` — summarize the most recent automated scan (supports `--live`)
- `wks0 vault sync` — force immediate vault sync (normally automatic)
- `wks0 db vault` — query the underlying collection

### Transform Layer

**Purpose**: Binary → Text conversion with caching (not extraction)

**Database**: `wks.transform` collection
- `file_uri` — File URI (file:// scheme)
- `checksum` — SHA-256 of original file content
- `size_bytes` — Original file size
- `last_accessed` — ISO timestamp of last cache access
- `created_at` — ISO timestamp of transform creation
- `engine` — Transform engine name (e.g., "docling")
- `options_hash` — Hash of engine options used
- `cache_location` — Path to cached transformed file

**Cache**:
- Location: `.wks/transform/cache/`
- Max size: 1GB (configurable via `transform.cache.max_size_bytes`)
- Eviction: LRU (least recently used)
- Cache key: `hash(file_content + engine + options)`
- Format: `<cache_dir>/<checksum>.<extension>`

**Cache Management**:
- Simple JSON file (`.wks/transform/cache.json`) tracks total cache size
- On new transform: check if adding size exceeds limit
- If would exceed: query DB for oldest files (by `last_accessed`), evict until space available
- Update JSON with new total size

**Engines**:
- `docling` — PDF, DOCX, PPTX via IBM Docling
  - Config: `max_chars: -1` (infinite for full documents)
  - Default output: markdown

**Monitor Integration**:
- File moved: update `file_uri` in transform DB
- File modified/deleted: remove entry from transform DB

**Commands**:
- `wks0 transform docling file.pdf` — transform and output cache checksum
- `wks0 transform docling file.pdf -o output.md` — transform and write to file
- `wks0 db transform` — query transform database

**Notes**:
- No router, no defaults — explicit engine required
- Transform is cached conversion, not data extraction
- Each engine supports different options

### Diff Layer

**Purpose**: Calculate differences between file versions

**Engine Classes**:
1. **Binary** — Operates on bytes directly
   - `bsdiff3` — Binary diff using bsdiff3 algorithm
   - No content type requirements

2. **Text** — Operates on text with supported encodings
   - `myers` — Text diff using Myers algorithm
   - Requires text content or supported encoding
   - Fails fast if file is not text/supported type

**Commands**:
- `wks0 diff bsdiff3 file1.bin file2.bin` — binary diff
- `wks0 diff myers file1.txt file2.txt` — text diff
- `wks0 diff myers <checksum_a> <checksum_b>` — diff cached transforms
- `wks0 diff myers $(wks0 transform docling a.pdf) $(wks0 transform docling b.pdf)` — compose with transform

**Engine Options**:
- Each engine supports different options
- Examples: `--context-lines`, `--output-format`
- No standard diff result format (engine-specific)

**Notes**:
- No auto-transform — explicit engine and files only
- No router, no defaults
- Fail immediately if content type doesn't match engine requirements
- No database for diff operations
- Diff operates on original file formats or explicit transforms

**MCP Integration**: Diff engines can be exposed as MCP tools

### Search Layer

**Purpose**: Query interface for finding files and content across the knowledge base

**Capabilities**:
- Natural language search across indexed documents
- Semantic similarity search
- Combined weighted search across multiple indices
- Filter by file type, priority, vault membership

**Query Interface**:
```bash
wks0 search "machine learning papers"
wks0 search "related to project Alpha" --vault-only
wks0 search "python functions using asyncio" --index code
```

**Architecture**:
- Builds on Index Layer for actual search execution
- Combines results from multiple indices with configurable weights
- Respects monitor priority for result ranking
- Uses transform layer for searchable content extraction

**Index Integration**:
- `--index main` - Search document embeddings (default)
- `--index code` - Search code structure/AST
- `--combine` - Weighted combination of all enabled indices

### Index Layer

**Purpose**: Maintain searchable indices of file content and structure

**Index Types**:
- **Document Index (RAG)**: Embedding-based semantic search
  - Text extraction via Transform Layer
  - Chunk-based indexing with overlap
  - Vector similarity search
  
- **Code Index (AST)**: Structure-aware code search
  - Parse source files into AST
  - Index functions, classes, imports
  - Symbol-level search and navigation

**Architecture**:
- Each index is independent with its own database
- Indices built on top of Transform and Monitor layers
- Transform provides content extraction
- Monitor provides file discovery and priorities

**Database Schema** (per index):
```python
{
  "file_uri": "file:///path/to/file",
  "checksum": "sha256...",
  "chunks": [...],
  "embedding": [...],
  "metadata": {
    "priority": 95,
    "vault_member": false,
    "index_name": "main"
  }
}
```

**Commands**:
```bash
wks0 index build main          # Build/rebuild main index
wks0 index build code          # Build code index
wks0 index status              # Show index statistics
wks0 db index                  # Query index database
```

**Integration**:
- Monitor events trigger incremental index updates
- Transform layer provides searchable content
- Vault membership affects index priority
- MCP tools expose search capabilities to AI assistants

## Database Commands

All layers store data in MongoDB:

```bash
# Query databases
wks0 db monitor              # Filesystem state
wks0 db vault                # Knowledge graph links
wks0 db transform            # Transform cache metadata

# Reset databases (destructive)
wks0 db reset monitor        # Clear filesystem state
wks0 db reset vault          # Clear link graph
wks0 db reset transform      # Clear transform cache and DB
```

## Service Management

```bash
wks0 service install         # Install launchd service (macOS)
wks0 service uninstall       # Remove service
wks0 service start           # Start daemon
wks0 service stop            # Stop daemon
wks0 service restart         # Restart daemon
wks0 service status          # Show status and metrics (supports --live for auto-updating display)
```

## Config Management

```bash
wks0 config                  # Print effective config (table in CLI, JSON in MCP)
```

## Priority Scoring Details

### Managed Directory Mapping

| Directory       | Priority        | Purpose                          |
|-----------------|-----------------|----------------------------------|
| `~/Desktop`     | 150             | Current week's work (symlinks)   |
| `~/deadlines`   | 120             | Time-sensitive deliverables      |
| `~`             | 100             | Active year-scoped projects      |
| `~/Documents`   | 100             | Finalized materials and archives |
| `~/Pictures`    | 80              | Visual assets (memes, figures)   |
| `~/Downloads`   | 50              | Temporary/unorganized staging    |

### Calculation Examples

**Example 1**: `/Users/ww5/Documents/my/full/_path/__file.txt`
- Matches: `~/Documents` (base = 100)
- `my`: 100 × 0.9 = 90
- `full`: 90 × 0.9 = 81
- `_path`: 81 × 0.9 × 0.5 = 36.45 (one underscore)
- `__file`: 36.45 × 0.9 × 0.25 = 8.20 (two underscores)
- Extension `.txt`: 8.20 × 1.0 = 8.20
- **Priority: 8**

**Example 2**: `/Users/ww5/deadlines/2025_12_15-Proposal/draft.pdf`
- Matches: `~/deadlines` (base = 120)
- `2025_12_15-Proposal`: 120 × 0.9 = 108
- Extension `.pdf`: 108 × 1.1 = 118.8
- **Priority: 119**

**Example 3**: `/Users/ww5/Downloads/_archive/old.txt`
- Matches: `~/Downloads` (base = 50)
- `_archive`: 50 × 0.9 × 0.5 = 22.5
- Extension `.txt`: 22.5 × 1.0 = 22.5
- **Priority: 23**

**Priority-Based Organization**:
- Files with higher priority scores are more accessible/discoverable
- Priority affects search ranking (when implemented)
- Underscore prefixes (`_old/`, `_drafts/`) automatically reduce priority

## MCP Integration

WKS exposes semantic engines and monitor operations as MCP tools. Following SPEC principles: zero code duplication with business logic in controllers, view-agnostic structured data, and both CLI and MCP using the same controller methods.

### Monitor Tools

Complete parity between CLI and MCP for filesystem monitoring:

**Status and Validation**:
- `wks_monitor_status` — Get monitoring status and configuration (`wks0 monitor status`)
- `wks_monitor_validate` — Validate configuration for conflicts (`wks0 monitor validate`)
- `wks_monitor_check` — Check if path would be monitored (`wks0 monitor check <path>`)

**List Management**:
- `wks_monitor_list` — Get contents of configuration list (`wks0 monitor <list_name>`)
  - Parameters: `list_name` (include_paths, exclude_paths, ignore_dirnames, ignore_globs)
- `wks_monitor_add` — Add value to list (`wks0 monitor <list_name> add <value>`)
  - Parameters: `list_name`, `value`
- `wks_monitor_remove` — Remove value from list (`wks0 monitor <list_name> remove <value>`)
  - Parameters: `list_name`, `value`

**Managed Directories**:
- `wks_monitor_managed_list` — List managed directories with priorities (`wks0 monitor managed`)
- `wks_monitor_managed_add` — Add managed directory (`wks0 monitor managed add <path> --priority <N>`)
  - Parameters: `path`, `priority`
- `wks_monitor_managed_remove` — Remove managed directory (`wks0 monitor managed remove <path>`)
  - Parameters: `path`
- `wks_monitor_managed_set_priority` — Update directory priority (`wks0 monitor managed set-priority <path> <N>`)
  - Parameters: `path`, `priority`

All write operations save to config file and notify to restart service.

### Vault Tools

Complete parity between CLI and MCP for Obsidian vault link tracking:

**Status and Reporting**:
- `wks_vault_status` — Get vault link status summary (`wks0 vault status`)
  - Returns: total_links, ok_links, missing_symlink, missing_target, legacy_links, external_urls, embeds, wiki_links, last_sync
- `wks_vault_links` — Get all links to/from a specific file (`wks0 vault links <path>`)
  - Parameters: `file_path`, `direction` (both/to/from, default: both)
  - Returns: file URI, monitor status, links_from, links_to
- `wks_vault_sync` — Sync vault links to MongoDB (`wks0 vault sync`)
  - Parameters: `batch_size` (optional, default: 1000)
  - Returns: sync statistics and status

All vault tools use VaultController and VaultStatusController business logic.

### Architecture

**MonitorController Methods** (in `wks/monitor/monitor_controller.py`):
- Read-only: `get_status()`, `get_list()`, `get_managed_directories()`, `validate_config()`, `check_path()`
- Write operations: `add_to_list()`, `remove_from_list()`, `add_managed_directory()`, `remove_managed_directory()`, `set_managed_priority()`

**VaultController Methods** (in `wks/vault/controller.py`):
- `sync_vault()` — Sync vault links to database
- `fix_symlinks()` — Fix legacy file:// links to vault:// URIs

**VaultStatusController Methods** (in `wks/vault/status_controller.py`):
- `summarize()` — Get vault status summary with link counts and issues

**MCP Server** (in `wks/mcp_server.py`):
1. JSON-RPC 2.0 protocol (stdio transport with Content-Length framing)
2. Loads configuration via `load_config()`
3. Routes tool calls to controller methods
4. Formats responses as structured JSON
5. Handles config file updates for write operations

**Installation**:
```bash
wks0 mcp install              # Install to all supported clients
wks0 mcp install --client cursor --client claude
```

**Running**:
```bash
wks0 mcp run                  # Proxies to background daemon broker
wks0 mcp run --direct         # Run inline for debugging
```

**Testing**: All MCP tools verified working via integration tests.

## Patterns (CLAUDE.md)

Organizational patterns are documented separately in `CLAUDE.md`. They describe:
- Where to place files physically (which managed directories)
- How to name files (date formats, conventions)
- When to archive (`_old/YYYY/`)
- How to organize content types (presentations, emails, etc.)

**Patterns provide organizational guidance**:
- Use `~/deadlines/YYYY_MM_DD-Name/` for time-sensitive work
- Use `~/YYYY-ProjectName/` for active projects
- Use `_old/YYYY/` for hierarchical archiving
- Use `_drafts/` to deprioritize working documents

The system calculates priorities automatically based on file placement.
