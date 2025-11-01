# WKS Command-Line Utility (wkso)

This spec documents the wkso CLI: a minimal, focused interface to configure, run, and index the WKS agent. It intentionally covers only three command groups: config, service, and index.

## Overview
- Purpose: Keep filesystem and Obsidian in sync, maintain embeddings + change history, and expose raw document extractions for downstream tooling.
- Scope: Single CLI `wkso` with commands:
  - `wkso config` — inspect effective configuration
  - `wkso service` — install/start/stop the background daemon (macOS launchd support)
  - `wkso extract` — run the configured extractor on one or more documents and persist their plain-text form
  - `wkso index` — extract + embed files/directories into the similarity "space" database with Docs output
  - `wkso db` — query or reset Mongo collections that back the space/time databases

## Installation
- Recommended: pipx
  - `pipx install .`
  - If using Docling extraction: `pipx runpip wkso install docling`
- Python: 3.10+

## Configuration
- Stored at `~/.wks/config.json`. All keys shown below are required unless noted optional.

```json
{
  "vault_path": "~/obsidian",
  "obsidian": {
    "base_dir": "WKS",
    "log_max_entries": 500,
    "active_files_max_rows": 50,
    "source_max_chars": 40,
    "destination_max_chars": 40,
    "docs_keep": 99
  },
  "monitor": {
    "include_paths": ["~"],
    "exclude_paths": ["~/Library", "~/obsidian", "~/.wks"],
    "ignore_dirnames": [".git", "_build"],
    "ignore_globs": ["*.tmp", "*~", "._*"],
    "state_file": "~/.wks/monitor_state.json"
  },
  "activity": { "state_file": "~/.wks/activity_state.json" },
  "display": { "timestamp_format": "%Y-%m-%d %H:%M:%S" },
  "mongo": {
    "uri": "mongodb://localhost:27027/",
    "space_database": "wks_similarity",
    "space_collection": "file_embeddings",
    "time_database": "wks_similarity",
    "time_collection": "file_snapshots"
  },
  "extract": {
    "engine": "docling",
    "ocr": false,
    "timeout_secs": 30,
    "options": {}
  },
  "similarity": {
    "enabled": true,
    "model": "all-MiniLM-L6-v2",
    "include_extensions": [".md", ".txt", ".py", ".ipynb", ".tex", ".docx", ".pptx", ".pdf", ".html", ".csv", ".xlsx"],
    "min_chars": 10,
    "max_chars": 200000,
    "chunk_chars": 1500,
    "chunk_overlap": 200,
    "offline": true,
    "respect_monitor_ignores": false
  }
}
```
- `display.timestamp_format` governs every timestamp printed by the CLI and Obsidian surfaces.
- `extract.*` is forwarded to the extractor implementation; Docling must honor `engine`, `ocr`, `timeout_secs`, and any values inside `options`.
- `similarity.include_extensions` limits which files are processed; extraction always runs through the `extract` config prior to embedding.

## Commands

Global options:
- `--version` — print the installed CLI version (with current git SHA when available) and exit immediately.
- `--display {auto,rich,json}` — select the output style for subcommands (default `rich`).
- Service status summary surfaces DB heartbeat/last operation, weighted FS activity rates, and supports JSON/Markdown output alongside Rich tables.
- Config `metrics` block tunes filesystem rate smoothing (`fs_rate_short_window_secs`, `fs_rate_long_window_secs`, `fs_rate_short_weight`, `fs_rate_long_weight`).

### wkso config
- `wkso config print` — print the effective JSON config to stdout.

### wkso service
- Purpose: Manage the long‑running daemon that monitors files, writes FileOperations/ActiveFiles/Health in `~/obsidian/<base_dir>`, and updates embeddings.
- macOS launchd:
  - `wkso service install` — write `~/Library/LaunchAgents/com.wieselquist.wkso.plist`, bootstrap, and start.
  - `wkso service install` ensures the configured MongoDB endpoint is reachable; when using the default `localhost:27027`, it auto-starts a local `mongod` if needed.
  - `wkso service uninstall` — unload and remove the plist (cleans up legacy labels).
- Start/stop/status (works with or without launchd):
  - `wkso service start` — verify Mongo is running (auto-start local `mongod` when configured), then start via launchd if installed, else start a background process.
  - `wkso service stop` — stop the running daemon and shut down the managed `mongod` if we launched it.
  - `wkso service status` — print daemon status.
  - `wkso service restart` — restart daemon (via launchd if present).

Database responsibilities
- The service maintains a file database keyed by path that tracks: path, checksum, embedding, date last modified, last operation, number of bytes, and angle from empty (the angle between the file’s embedding and the embedding of the empty string). Embeddings are computed per the configured strategy (Docling extraction + sentence-transformers as currently deployed).
- The database powers de‑duplication, similarity checks, and RAG‑like queries. Moves/renames are recognized via matching checksum so we avoid creating new logical entries on path changes. We do not use the checksum as the primary key; path remains the key so when a file at a path is updated, all metadata updates in place without changing the key.
- The daemon runs a background maintenance loop (default cadence ≈10 minutes) that calls `SimilarityDB.audit_documents()` to prune missing files, clear stale extraction artefacts, refresh stored byte counts, and normalize legacy records (plain filesystem paths → `file://` URIs). Shutdown waits for the current audit to finish so the Mongo client can close cleanly.
- Primary views today:
  - `FileOperations.md`: a Markdown view of the top N most recent changes. It should show checksum, date last modified, last operation, human‑readable size, and angle from empty (or `-` if unavailable). Temp/autosave artifacts are hidden in this view.
- `Health.md`: a dashboard of current status and metrics.

Change Snapshots Database (planned)
- Purpose: Maintain a time-dependent history of content changes per file, respecting moves/renames and avoiding duplicate logical entries.
- Key behaviors:
  - Path remains the primary identity; moves/renames do not create new logical entries when the checksum is unchanged (records are renamed in-place).
  - On content change, create a snapshot record with: `path`, `t_prev`, `t_new`, `checksum_new`, `checksum_prev`, `bytes_delta`, `size_bytes_new`, `size_bytes_prev`, `angle_delta` (from embedding_changes), and `binary_patch_size` (size in bytes from bsdiff4 on previous vs new content). Binary diff runs for every change, regardless of embedding availability.
  - History access: must be able to list all change times in the past week per file, and always include at least the most recent modification.
- Implementation notes:
  - Collection name: `file_snapshots` (MongoDB). Indices on `(path, t_new_epoch)`.
  - Binary diff: use `bsdiff4.file_diff(old, new, patch)` to compute a temp patch, measure size, and dispose; store `binary_patch_size` only (not the patch content).
  - Angle from empty and change angle derive from the embedding DB: `angle_delta` aligns with entries in `embedding_changes`.
  - Large files: consider a configurable size cap for diffing; still record metadata when skipped.

Notes
- Single instance enforced via `~/.wks/daemon.lock`.
- Health: `~/.wks/health.json` and `~/obsidian/<base_dir>/Health.md`.
- FileOperations: rebuilt from `~/.wks/file_ops.jsonl` with temp/autosaves hidden in the page view.

### wkso extract
- Purpose: Run the configured extractor on one or more files and persist the plain-text output for reuse.
- Usage:
  - `wkso extract <source ...> [--output DIR]`
- Behavior:
  - Verifies each source path against `monitor` include/ignore rules, then invokes the engine described in `config.extract` (Docling by default).
  - Extraction settings (`engine`, `ocr`, `timeout_secs`, and `options`) are honored exactly as supplied in config.
  - Output defaults to `~/obsidian/<base_dir>/Docs/<content-hash>.md`. When `--output DIR` is supplied, the results are written to that directory using the same hash-based filenames.
  - Produces UTF-8 Markdown only; no embeddings are generated. Downstream commands (e.g., `wkso index`) may reuse the extracted text directly when re-indexing.

### wkso index
- Purpose: Extract + embed files and directories into the space database and refresh Docs snapshots.
- Usage:
  - `wkso index <path ...>` — each path may be a file or directory; directories are processed recursively.
  - `wkso index --untrack <path ...>` — remove tracked entries (and their extraction artefacts) from the space/time databases without deleting the source files.
- Behavior:
  - Filters files by `similarity.include_extensions`.
  - For each file: invokes the same extraction pipeline used by `wkso extract` (reusing cached output when the content hash is unchanged), computes embeddings, records change angle, and writes `~/obsidian/<base_dir>/Docs/<checksum>.md` when updated.
  - Shows a progress bar with ETA and current filename; prints a final summary.

### wkso db
- Purpose: Provide lightweight access to the Mongo databases that power similarity (space) and change snapshots (time) without requiring Docling/model startup.
- Subcommands:
  - `wkso db query --space|--time [--filter JSON] [--projection JSON] [--sort field:asc|desc] [--limit N]` — run raw Mongo queries against the selected logical store.
    - `--space` targets the embeddings collection (`similarity.collection`, default `file_embeddings`).
    - `--time` targets the snapshots collection (`similarity.snapshots_collection`, default `file_snapshots`).
    - Works with minimal config: `mongo.uri`, `mongo.space_database`, and `mongo.space_collection`; all default to the canonical values if missing.
  - `wkso db info [--space|--time] [-n N]` — print counts and list the most recent files/snapshots using short Mongo timeouts for responsiveness.
    - Defaults to the space database when neither `--space` nor `--time` is supplied.
    - `-n/--latest` shows the latest N entries (default 10).
    - When using the default local URI, the command auto-starts `mongod` if it is not already running.
    - Space view columns (in order): human-readable timestamp (respecting `display.timestamp_format`), checksum, human-readable size, angle, and absolute URI.
    - Time/snapshot view columns include: `t_new`, path, checksum, extracted size, and byte delta.
  - `wkso db reset` — drop the configured database and remove the local `~/.wks/mongodb` data directory; best-effort stop of local `mongod` on port 27027.
- Error handling: all db commands report connection failures succinctly (`DB connection failed`/`DB unreachable`) and exit non‑zero when Mongo cannot be reached.

## Output Surfaces (daemon)
- `WKS/FileOperations.md` — reverse chronological operations log (auditable ledger; temp/autosaves hidden in view).
- `WKS/ActiveFiles.md` — sorted by |°/hr| from embedding_changes (1h/1d/1w windows; sign preserved).
- `WKS/Health.md` — heartbeat, metrics, links.
- `WKS/Docs/` — extracted text snapshots by checksum (latest N kept).

## Safety & Defaults
- Writes only under `~/obsidian/<base_dir>`.
- Respects ignore rules (`exclude_paths`, `ignore_dirnames`, `ignore_globs`).
- Avoids duplicate daemons; stale locks are cleaned when possible.

## Databases

### Space database (`mongo.space_collection`)
- Storage: MongoDB. Production deployments must provide a reachable Mongo instance; the local CLI auto-starts `mongod` on `localhost:27027` when using defaults.
- Primary key: absolute URI string (e.g., `file:///Users/.../README.md`). Future remote providers must normalize their paths to absolute URIs as well.
- Required fields for each document:
  - `path` — absolute URI (string, primary key)
  - `timestamp` — ISO 8601 UTC string for the last observed modification
  - `checksum` — cryptographic checksum (sha256 by default) of the raw file
  - `bytes` — raw file size in bytes
  - `content_path` — path to the extracted content generated by the active extractor
  - `embedding` — floating-point vector representing the extracted content
  - `angle` — degrees between the embedding and the “empty string” embedding

Extraction artefacts live alongside the source file in a `.wkso/` sibling directory:
`basedir(<path>)/.wkso/<checksum>.<ext>`. The extension is dictated by the extractor (Docling currently emits `.md`). When a file’s checksum changes or it moves, the old extraction files MUST be removed.

- Behavioural requirements:
  - Re-indexing the same file updates the existing record in-place (no duplicate rows).
  - Moves or renames reuse the same logical record (identified by checksum); we update `path`, keeping history in the time database.
  - The space database powers similarity, duplicate detection, and `wkso db info/query --space`.
  - `wkso db info` (space view) MUST display, in order: human-readable timestamp (respecting `display.timestamp_format`), checksum, human-readable size, angle, and the file URI.
  - `wkso index <file>` adds or refreshes entries; `wkso index --untrack <file>` removes the space/time records and associated extraction artefacts. Filesystem moves detected by the WKS service register as modifications with updated timestamps.

### Time (snapshot) database (`mongo.time_collection`)
- Captures per-change history for each logical file:
  - `path`, `t_prev`, `t_new`
  - `checksum_prev`, `checksum_new`
  - `size_bytes_prev`, `size_bytes_new`, `bytes_delta`
  - `binary_patch_size`, `angle_delta`
- Records are append-only. On rename we update existing entries to the new path.
- Consumers should index `(path, t_new_epoch)` for efficient lookups.

### Supporting collections
- `embedding_changes` — rolling window statistics that feed ActiveFiles (degrees/hour, etc.).
- `file_moves` — durable queue of path transitions produced by the monitor. Each record captures `path_before`, `path_after`, `event_ts`, `is_directory`, and the list of descendant URIs (for directories) so that Obsidian link rewrites and Docs refreshes can be applied idempotently. Entries are marked processed once both the space database and the vault links have been updated.
- `file_chunks` — chunk-level search index. Each row describes a slice of a file with fields: `path` (URI, same as space db), `chunk_index`, `chunk_hash`, `text`, `embedding`, and optional metadata (page number, heading). This collection is optimized for retrieval-augmented generation and search APIs.
- Any future helper collections must be documented here before adoption.
