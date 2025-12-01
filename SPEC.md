# WKS (Wieselquist Knowledge System)

A layered architecture for filesystem monitoring, knowledge graph management, and semantic indexing.

**Primary Interface**: The **MCP Server** is the source of truth for all capabilities, allowing AI agents to fully control the system.
**Secondary Interface**: The `wksc` CLI provides human-friendly equivalents for all MCP tools.

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

## Configuration

**Config Location**: `~/.wks/config.json` (default)

The config directory can be customized via the `WKS_HOME` environment variable:
```bash
export WKS_HOME="/custom/path"  # Config at /custom/path/config.json
```

**Viewing Configuration**:
```bash
wksc config    # Print effective config (table in CLI, JSON in MCP)
```

**Top-Level Structure**:

```json
{
  "monitor": { /* Filesystem tracking configuration */ },
  "vault": { /* Knowledge graph configuration */ },
  "db": { /* MongoDB connection settings */ },
  "transform": { /* Document conversion engines */ },
  "diff": { /* Comparison engines */ },
  "index": { /* Search indices */ },
  "search": { /* Search behavior */ },
  "display": { /* UI formatting */ }
}
```

## Monitor Layer

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

**Monitor include/exclude logic**:
- `include_paths` and `exclude_paths` store canonical directories (fully-resolved on load). A path must appear in exactly one list; identical entries across both lists are a validation error. When evaluating a file/directory, resolve it and walk its ancestors until one appears in either list. The nearest match wins. If the closest ancestor is in `exclude_paths` (or no ancestor is found at all), the path is excluded immediately and no further checks run.
- Once a path survives the root check, the daemon applies directory/glob rules in two phases:
  - **Exclusion phase**: evaluate `exclude_dirnames` (the immediate parent directory) and `exclude_globs` (full path/basename). If either matches, the path becomes “tentatively excluded”.
  - **Inclusion overrides**: evaluate `include_dirnames` and `include_globs`. If a path was tentatively excluded but matches an include rule, the exclusion is reversed and the path is monitored. If neither include rule fires, the exclusion stands. Dirname/glob lists must not share entries; duplicates are validation errors, and entries that duplicate the opposite glob list are flagged as redundant.

### MCP Interface (Primary)

Complete control over monitoring configuration and status.

- `wksm_monitor_status` — Get monitoring status and configuration
- `wksm_monitor_validate` — Validate configuration for conflicts
- `wksm_monitor_check(path)` — Check if path would be monitored
- `wksm_monitor_list(list_name)` — Get contents of configuration list
- `wksm_monitor_add(list_name, value)` — Add value to list
- `wksm_monitor_remove(list_name, value)` — Remove value from list
- `wksm_monitor_managed_list` — List managed directories
- `wksm_monitor_managed_add(path, priority)` — Add managed directory
- `wksm_monitor_managed_remove(path)` — Remove managed directory
- `wksm_monitor_managed_set_priority(path, priority)` — Update directory priority
- `wksm_db_monitor()` — Query filesystem database

### CLI Interface (Secondary)

Human-friendly wrappers for the MCP tools.

- `wksc monitor status` — show monitoring statistics (supports `--live`)
- `wksc monitor include_paths {add,remove} <path>` — manage explicit inclusions
- `wksc monitor exclude_paths {add,remove} <path>` — manage explicit exclusions
- `wksc monitor include_dirnames {add,remove} <name>` — manage directory name inclusions
- `wksc monitor exclude_dirnames {add,remove} <name>` — manage directory name exclusions
- `wksc monitor include_globs {add,remove} <pattern>` — manage glob pattern inclusions
- `wksc monitor exclude_globs {add,remove} <pattern>` — manage glob pattern exclusions
- `wksc monitor managed {add,remove,set-priority}` — manage directory priorities
- `wksc db monitor` — query filesystem database

## Vault Layer

**Goal**: Manage a knowledge vault that links transient priorities to monitored file system resources. 

**Database**: `wks.vault`

**URI-First Design**: All links stored as cross-platform URIs. Local filesystem paths derived on-demand from URIs.

### Symlink Naming Convention

The notes within the vault links the knowledge managed contained in the file system. The vault should not have significant knowledge but focus on connecting things. It changes with time and this is managed within git within the repo.
There should be git hooks that are deployed by WKS to help manage snapshots of the vault. For example, we do not commit files until we are sure all the links are healthy. Obsidian is the prototype vault and for any files external to the vault, we create a symlink within the vault so that the files and directories can be treated like internal files to the vault. 

External files are mirrored under `_links/<machine>/` to match filesystem structure:
```
_links/
  mbp-2021/
    Users/ww5/Documents/papers/paper.pdf → /Users/ww5/Documents/papers/paper.pdf
    Users/ww5/2025-ProjectName/README.md → /Users/ww5/2025-ProjectName/README.md
```

### Schema

Each link becomes exactly one document. `_id` is `sha256(note_path + line_number + to_uri)` so repeated scans upsert deterministically. Fields are grouped as follows:

1. **Source context**
   - `note_path`: note path relative to vault root (stored in VaultEdgeRecord, not in DB document)
   - `from_uri`: cross-platform URI to source note (e.g., `vault:///Projects/Foo.md`)
   - `line_number`: 1-based line that produced the link
   - `source_heading`: nearest markdown heading text (empty string if none)
   - `raw_line`: full line content trimmed to a safe length for debugging

2. **Link content**
   - `link_type`: `wikilink`, `embed`, or `markdown_url`
   - `raw_target`: text inside the link (`[[…]]` target or `(…)` URL), including alias
   - `alias_or_text`: alias or `[text]` label (empty string when not supplied)

3. **Target resolution (URI-first)**
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

### MCP Interface (Primary)

- `wksm_vault_status` — Get vault link status summary
  - Returns: total_links, ok_links, missing_symlink, missing_target, legacy_links, external_urls, embeds, wiki_links, last_sync
- `wksm_vault_links(file_path, direction)` — Get all links to/from a specific file
  - Parameters: `file_path`, `direction` (both/to/from, default: both)
  - Returns: file URI, monitor status, links_from, links_to
- `wksm_vault_sync(batch_size)` — Sync vault links to MongoDB
  - Parameters: `batch_size` (optional, default: 1000)
  - Returns: sync statistics and status
- `wksm_vault_validate()` — Validate all vault links
- `wksm_vault_fix_symlinks()` — Rebuild _links/<machine>/ from vault DB
- `wksm_db_vault()` — Query vault database

### CLI Interface (Secondary)

- `wksc vault status` — summarize the most recent automated scan (supports `--live`)
- `wksc vault sync` — force immediate vault sync (normally automatic)
- `wksc vault validate` — validate all vault links (check for broken links)
- `wksc vault fix-symlinks` — rebuild _links/<machine>/ from vault DB
- `wksc vault links <path>` — show all links to and from a specific file
- `wksc db vault` — query the underlying collection

## Transform Layer

Converts binary documents (PDF, DOCX, PPTX) to text/markdown for searching, indexing, and comparison.

**Why Transform Exists**:
- Binary documents can't be searched, indexed, or compared as-is
- AI agents need text content to reason about documents
- Text diff tools need text representation to show meaningful changes
- Search/index layers need extracted text content

**Caching**: Transformations are computationally expensive (OCR, layout analysis), so results are cached with LRU eviction.

### Engines

The system is written to support multiple engines. Docling is used as a prototype.

### Database Schema

Collection: `wks.transform`

- `file_uri` — File URI (file:// scheme)
- `checksum` — SHA-256 of original file content
- `size_bytes` — Original file size
- `last_accessed` — ISO timestamp of last cache access
- `created_at` — ISO timestamp of transform creation
- `engine` — Transform engine name (e.g., "docling")
- `options_hash` — Hash of engine options used
- `cache_location` — Path to cached transformed file

### MCP Interface (Primary)

- `wksm_transform(file_path, engine, options)` — Transform a file using a specific engine. Returns checksum.
- `wksm_cat(target)` — Retrieve content. `target` can be a checksum or a file path (auto-transforms if needed).
- `wksm_db_transform()` — Query transform database.

### CLI Interface (Secondary)

- `wksc transform` — Transform a file (e.g., `wksc transform docling file.pdf`)
- `wksc cat` — Retrieve content (e.g., `wksc cat <checksum>` or `wksc cat <file>`)
- `wksc db transform` — Query transform database

## Diff Layer

**Purpose**: Calculate differences between files

The diff layer supports an arbitrary number of engines but for prototype purposes,
we consider a binary and text diff.

1. **Binary** — Operates on bytes directly
   - `bsdiff3` — Binary diff using bsdiff3 algorithm
   - No content type requirements

2. **Text** — Operates on text with supported encodings
   - `myers` — Text diff using Myers algorithm
   - Requires text content or supported encoding
   - Fails fast if file is not text/supported type

3. **Code** — Operates on code with supported languages
   - `ast` — Code AST diff
   - Requires code content or supported language
   - Fails fast if file is not code/supported language

**Diffing Transformed Content**:
Since transformations (e.g., PDF to Markdown) create new representations of content, the diff layer explicitly supports diffing via checksums. These checksums are returned by the Transform Layer (`wksm_transform`) and refer to the cached transformed content. This allows comparing different transformations of a document.

**Diffing Indices**:
Indices (e.g., Code AST, Document Embeddings) can be diffed to reveal semantic or structural changes. For example, diffing two Code AST indices can show which functions were added or modified, ignoring formatting changes.

### MCP Interface (Primary)

- `wksm_diff(engine, target_a, target_b)` — Calculate diff between two targets (files, checksums, or indices).

### CLI Interface (Secondary)

- `wksc diff` — Calculate diff (e.g., `wksc diff <engine> <file_a> <file_b>` or `wksc diff <engine> <checksum_a> <checksum_b>`)

## Index Layer

**Purpose**: Maintain searchable indices of file content and structure

Indices are populated based on rules that chain a transform to an embedding scheme to a database. Two main types of embeddings shall be supported:

1. **Document Embeddings** — Operates on documents
2. **Code Embeddings** — Operates on code

An index typically supports both a diff and a search.

Multiple indices are supported but the main type of index is embedding, RAG-type models.

We will also support the BM25 index for simple text search.

### MCP Interface (Primary)

- `wksm_index_list()` — List available indices
- `wksm_index_create(index_name, index_type)` — Create a new index
- `wksm_index_add(index_name, file_path)` — Add a specific file to the index
- `wksm_index_build(index_name)` — Build/rebuild index
- `wksm_index_status(index_name)` — Show index statistics
- `wksm_index_rule_add(index_name, pattern, engine)` — Add indexing rule
- `wksm_index_rule_remove(index_name, pattern)` — Remove indexing rule
- `wksm_index_rule_list(index_name)` — List indexing rules
- `wksm_db_index(index_name)` — Query index database

### CLI Interface (Secondary)

- `wksc index list` — List available indices
- `wksc index create <index_name> <index_type>` — Create a new index
- `wksc index add <index_name> <file>` — Add a specific file to the index
- `wksc index build <index_name>` — Build/rebuild index
- `wksc index status <index_name>` — Show index statistics
- `wksc index rule add <index_name> <pattern> <engine>` — Add indexing rule
- `wksc index rule remove <index_name> <pattern>` — Remove indexing rule
- `wksc index rule list <index_name>` — List indexing rules
- `wksc db index <index_name>` — Query index database

## Search Layer

**Purpose**: Query interface for finding files and content across the knowledge base

Multiple search types are supported but the main new search type is through Vespa AI.

**Capabilities**:
- Natural language search across indexed documents
- Semantic similarity search
- Combined weighted search across multiple indices

### MCP Interface (Primary)

- `wksm_search(query, indices, limit)` — Execute search query

### CLI Interface (Secondary)

- `wksc search "machine learning papers"`
- `wksc search "related to project Alpha" --vault-only`
- `wksc search "python functions using asyncio" --index <index_name>`

## Patterns Layer

**Vision**: Simple script-based organizational patterns with MCP server for AI access. Scripts are the source of truth for both code and documentation.

**Architecture**:
- **Location**: `~/.wks/patterns/` (configurable)
- **Format**: Executable scripts (bash, python, etc.)
- **Documentation**: Extracted from script header comments

**How It Works**:
- **Discovery**: WKS scans the patterns directory for executable scripts.
- **Documentation**: Header comments are parsed to provide tool descriptions.
- **Execution**: Scripts are executed directly by CLI or MCP.

### MCP Interface (Primary)

- `wksm_pattern_list()` — List available patterns
- `wksm_pattern_run(name, args)` — Execute a pattern script
- `wksm_pattern_show(name)` — Show pattern documentation

### CLI Interface (Secondary)

- `wksc pattern list` — List available patterns
- `wksc pattern run <name> [args...]` — Execute a pattern script
- `wksc pattern show <name>` — Show pattern documentation

## Infrastructure

### Database

All layers store data in MongoDB:

```bash
# Query databases
wksc db monitor              # Filesystem state
wksc db vault                # Knowledge graph links
wksc db transform            # Transform cache metadata

# Reset databases (destructive)
wksc db reset monitor        # Clear filesystem state
wksc db reset vault          # Clear link graph
wksc db reset transform      # Clear transform cache and DB

### Service

**MCP Interface**:
- `wksm_service(action)` — Manage service (start, stop, restart, status, install, uninstall)

**CLI Interface**:
```bash
wksc service install         # Install launchd service (macOS)
wksc service uninstall       # Remove service
wksc service start           # Start daemon
wksc service stop            # Stop daemon
wksc service restart         # Restart daemon
wksc service status          # Show status and metrics (supports --live for auto-updating display)
```

### MCP Server

WKS exposes layers as MCP tools for AI assistant integration. Following SPEC principles: zero code duplication with business logic in controllers, view-agnostic structured data, and both CLI and MCP using the same controller methods.

**Installation**:
```bash
wksc mcp install              # Install to all supported clients
wksc mcp install --client cursor --client claude
```

**Running**:
```bash
wksc mcp run                  # Proxies to background daemon broker
wksc mcp run --direct         # Run inline for debugging
```
