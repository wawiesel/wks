# WKS Command-Line Utility (wks0)

This spec documents the wks0 CLI: a layered architecture for filesystem monitoring, knowledge graph management, and semantic indexing.

## Architecture Overview

WKS is built as a stack of independent, composable layers:

```
┌─────────────────────────────────────────────────────┐
│  Patterns (CLAUDE.md)                                │
│  Organizational guidance, not configuration          │
└─────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────┐
│  Search Layer                                        │
│  Combines indices with weights                       │
└─────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────┐
│  Index Layer                                         │
│  Multiple independent indices (RAG, AST, etc.)       │
└─────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────┐
│  Semantic Engines (pluggable)                        │
│  Related | Diff | Extract                            │
│  Each with _router for engine selection              │
└─────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────┐
│  Vault Layer (Obsidian)                              │
│  Knowledge graph: links only                         │
│  DB: wks.vault                                       │
└─────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────┐
│  Monitor Layer                                       │
│  Filesystem state: paths, checksums, priorities      │
│  DB: wks.monitor                                     │
└─────────────────────────────────────────────────────┘
```

## Installation
- Recommended: `pipx install .`
- Optional: `pipx runpip wks0 install docling` (for PDF/Office extraction)
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
      },
      "auto_index_min": 2
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

  "extract": {
    "output_dir_rules": {
      "resolve_symlinks": true,
      "git_parent": true,
      "underscore_sibling": true
    },
    "engines": {
      "docling": {
        "enabled": true,
        "is_default": true,
        "ocr": false,
        "timeout_secs": 30,
        "write_extension": "md"
      },
      "builtin": {
        "enabled": true,
        "max_chars": 200000
      }
    },
    "_router": {
      "rules": [
        {"extensions": [".pdf", ".docx", ".pptx"], "engine": "docling"},
        {"extensions": [".txt", ".md", ".py"], "engine": "builtin"}
      ],
      "fallback": "builtin"
    }
  },

  "diff": {
    "engines": {
      "bdiff": {
        "enabled": true,
        "is_default": true,
        "algorithm": "bsdiff"
      },
      "text": {
        "enabled": true,
        "algorithm": "unified",
        "context_lines": 3
      }
    },
    "_router": {
      "rules": [
        {"extensions": [".txt", ".md", ".py", ".json"], "engine": "text"},
        {"mime_prefix": "text/", "engine": "text"}
      ],
      "fallback": "bdiff"
    }
  },

  "related": {
    "engines": {
      "embedding": {
        "enabled": true,
        "is_default": true,
        "model": "all-MiniLM-L6-v2",
        "min_chars": 10,
        "max_chars": 200000,
        "chunk_chars": 1500,
        "chunk_overlap": 200,
        "offline": true,
        "database": "wks_similarity",
        "collection": "file_embeddings"
      },
      "diff_based": {
        "enabled": false,
        "threshold": 0.7,
        "database": "wks_similarity",
        "collection": "diff_similarity"
      }
    },
    "_router": {
      "default": "embedding",
      "rules": [
        {"priority_min": 50, "engine": "embedding"}
      ]
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

**Goal**: Keep vault markdown, `_links/` symlinks, and filesystem state aligned without manual intervention. The vault database is the bridge between the scanner and the monitor—no human-facing “fix it” commands exist.

**Database**: `wks.vault`

Each link becomes exactly one document (no optional fields; empty strings/zeros indicate “not applicable”). `_id` is `sha256(note_path + line_number + target_uri)` so repeated scans upsert deterministically. Fields are grouped as follows:

1. **Source context**
   - `note_path`: note path relative to the vault root (e.g., `Projects/Foo.md`).
   - `line_number`: 1-based line that produced the link.
   - `source_heading`: nearest markdown heading text (empty string if none).
   - `raw_line`: full line content trimmed to a safe length for debugging.

2. **Link content**
   - `link_type`: `wikilink`, `embed`, or `markdown_url`.
   - `raw_target`: text inside the link (`[[…]]` target or `(…)` URL).
   - `alias_or_text`: alias or `[text]` label (empty string when not supplied).
   - `is_embed`: `true` only for `![[…]]`.

3. **Target resolution**
   - `target_kind`: `vault_note`, `_links_symlink`, `external_url`, `attachment`, or `legacy_path`.
   - `target_uri`: normalized identifier for the link destination (`vault:///…`, `vault-link:///_links/...`, `https://…`).
   - `links_rel`: `_links/...` relative path when applicable, otherwise `""`.
   - `resolved_path`: absolute filesystem path reached at last scan (or `""`).
   - `resolved_exists`: boolean indicating whether the path existed.
   - `monitor_doc_id`: `_id` of the matching `wks.monitor` document or `""` if not yet indexed.

4. **Health & lifecycle**
   - `status`: `ok`, `missing_symlink`, `missing_target`, `legacy_link`, or `needs_monitor`.
   - `first_seen`: ISO timestamp from the initial scan that created the document.
   - `last_seen`: ISO timestamp from the latest scan that observed the link.
   - `last_updated`: ISO timestamp of the most recent write (scan or monitor-triggered).

A single metadata document (`_id = "__meta__"`, `doc_type = "meta"`) stores `last_scan_started_at`, `last_scan_duration_ms`, `notes_scanned`, `edges_written`, per-status counts, per-type counts, and the array `errors`. Status commands read this row instead of recomputing aggregates.

**Automation Workflow**:
1. **Monitor events** look up affected `resolved_path` values, rewrite markdown via `note_path`/`line_number`, refresh `_links/…`, and flip `status` plus `last_updated`.
2. **Scanner loop** runs on `vault.update_frequency_seconds`, parses every markdown file, validates `_links/…`, writes deterministic documents, and drops rows whose `_id` wasn’t touched (links removed from the vault).
3. **Status reporting** simply mirrors the persisted counts (`__meta__`) and lists unhealthy edges filtered by `status != "ok"`.

**Commands** (diagnostics only):
- `wks0 vault status` — summarize the most recent automated scan
- `wks0 db vault` — query the underlying collection

### Extract Layer

**Purpose**: Convert documents to plain text with pluggable engines

**Engines**:
- `docling` — PDF, DOCX, PPTX via IBM Docling
- `builtin` — Plain text files

**Router**: `_router` selects engine based on file extension

**Output Location Rules** (applied in order):
1. **Resolve symlinks**: Get real path before applying other rules
2. **Git parent**: If file is in git repo, place `.wkso/` above repo root
3. **Underscore sibling**: If any path component starts with `_`, place `.wkso/` as sibling to topmost `_`-prefixed directory
4. **Default**: Place `.wkso/` as sibling to source file

**Output Format**: `<.wkso_dir>/<checksum>.<extension>`

**Commands**:
- `wks0 extract <file>` — extract file with default engine
- `wks0 extract <file> --engine builtin` — force specific engine

**MCP Integration**: Extract engines can be exposed as MCP tools

### Diff Layer

**Purpose**: Calculate differences between file versions

**Engines**:
- `bdiff` — Binary diff (bsdiff algorithm)
- `text` — Unified text diff

**Router**: `_router` selects engine based on file type

**Commands**:
- `wks0 diff <file1> <file2>` — diff with default engine
- `wks0 diff <file1> <file2> --engine text` — force specific engine

**MCP Integration**: Diff engines can be exposed as MCP tools

### Related Layer

**Purpose**: Find semantically similar documents

**Engines**:
- `embedding` — Sentence transformer embeddings (all-MiniLM-L6-v2)
- `diff_based` — Similarity based on diff size

**Router**: `_router` selects engine based on context

**Database**: Each engine has its own database/collection

**Commands**:
- `wks0 related <file>` — find similar files
- `wks0 related <file> --limit 10 --min-similarity 0.5`
- `wks0 related <file> --engine embedding`

**MCP Integration**: Related engines can be exposed as MCP tools

### Index Layer

**Purpose**: Multiple independent indices for different use cases

**Indices**:
- `main` — General embedding-based index for documents
- `code` — AST-based index for code (optional)

**No Router**: Indexing is a decision, not routed automatically

**Schema** (per index):
- `path` — file URI
- `content_path` — extracted text location
- `embedding` — vector representation
- `angle` — degrees from empty string embedding
- `metadata` — index-specific metadata

**Commands**:
- `wks0 index <file>` — index with default index
- `wks0 index <file> --index code` — use specific index
- `wks0 index --untrack <file>` — remove from all indices

### Search Layer

**Purpose**: Query indices with optional combination

**Features**:
- Single index search (default)
- Multi-index search with weighted combination

**Commands**:
- `wks0 search <query>` — search default index
- `wks0 search <query> --index code` — search specific index
- `wks0 search <query> --combine` — search all indices with weights

## Database Commands

All layers store data in MongoDB:

```bash
# Query databases
wks0 db monitor              # Filesystem state
wks0 db vault                # Knowledge graph links
wks0 db related              # Similarity embeddings
wks0 db index                # Search indices

# Reset databases (destructive)
wks0 db reset monitor        # Clear filesystem state
wks0 db reset vault          # Clear link graph
wks0 db reset related        # Clear embeddings
wks0 db reset index          # Clear all indices
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

## Extraction Artefact Rules

Files extracted by the Extract layer are stored in `.wkso/` directories:

1. **Symlinks**: Resolve all symlinks before applying other rules
2. **Git repositories**: Place `.wkso/` one level above repository root (parent of `.git/`)
3. **Underscore-prefixed paths**: When any component starts with `_`, place `.wkso/` as sibling to topmost `_`-prefixed component
   - Example: `/Users/ww5/Documents/projects/_old/_previous/file.txt` → `/Users/ww5/Documents/projects/.wkso/`
4. **Default**: Place `.wkso/` as sibling to source file

When file checksum changes or file moves, old extraction files are removed.

## Priority Scoring Details

### Managed Directory Mapping

| Directory | Priority | Purpose |
|-----------|----------|---------|
| `~/Desktop` | 150 | Current week's work (symlinks) |
| `~/deadlines` | 120 | Time-sensitive deliverables |
| `~` | 100 | Active year-scoped projects |
| `~/Documents` | 100 | Finalized materials and archives |
| `~/Pictures` | 80 | Visual assets (memes, figures) |
| `~/Downloads` | 50 | Temporary/unorganized staging |

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

### Auto-Indexing Rules

- Files with priority < `auto_index_min` (default 2) are NOT auto-indexed
- Files inside `_/` subdirectories typically have priority 1
- Manual indexing via `wks0 index <path>` always succeeds regardless of priority

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

### Semantic Engine Tools

**Extract Tools**:
- `wks_extract` — extract document to plain text
- Parameters: `path`, `engine` (optional)

**Diff Tools**:
- `wks_diff` — compare two files
- Parameters: `path1`, `path2`, `engine` (optional)

**Related Tools**:
- `wks_related` — find similar documents
- Parameters: `path`, `limit`, `min_similarity`, `engine` (optional)

**Search Tools**:
- `wks_search` — semantic search across indices
- Parameters: `query`, `index` (optional), `limit`

### Architecture

**MonitorController Methods** (in `monitor_controller.py`):
- Read-only: `get_status()`, `get_list()`, `get_managed_directories()`, `validate_config()`, `check_path()`
- Write operations: `add_to_list()`, `remove_from_list()`, `add_managed_directory()`, `remove_managed_directory()`, `set_managed_priority()`

**MCP Server Responsibilities**:
1. JSON-RPC protocol (stdio transport)
2. Loading/saving configuration file
3. Routing tool calls to controllers
4. Formatting responses

**Implementation**: All functionality tested via unit tests (`test_monitor_controller.py`) and integration tests (`test_mcp_tools.py`).

## Patterns (CLAUDE.md)

Organizational patterns are documented separately in `CLAUDE.md`. They describe:
- Where to place files physically (which managed directories)
- How to name files (date formats, conventions)
- When to archive (`_old/YYYY/`)
- How to organize content types (presentations, emails, etc.)

**Patterns do NOT duplicate system mechanics like**:
- Priority calculation (defined in config)
- Indexing rules (defined in config)
- Extraction rules (defined in config)

**Patterns provide organizational guidance**:
- Use `~/deadlines/YYYY_MM_DD-Name/` for time-sensitive work
- Use `~/YYYY-ProjectName/` for active projects
- Use `_old/YYYY/` for hierarchical archiving
- Use `_drafts/` to deprioritize working documents

The system calculates priorities and handles indexing automatically based on where files are placed.
