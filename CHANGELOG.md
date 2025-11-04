# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and this project adheres to Semantic Versioning (SemVer).

## [0.2.8] - 2025-11-03
### Added
- Every Mongo database now stores a `_wks_meta` compatibility tag so upgrades can reuse existing embeddings when the schema is still compatible. Configure overrides via `mongo.compatibility.space|time` in `~/.wks/config.json`.
- `wkso db info/query` and the daemon status panel validate compatibility tags and explain how to override them instead of silently rebuilding the database.
- Optional Obsidian views that read `SimilarityDB` (Health/ActiveFiles) honor the same compatibility tags.
- Markdown outputs (service status, `db query`) now render through Jinja2 templates fed by the same JSON payloads used for `--display json`.

### Changed
- `wkso service`/daemon startup halts early when the stored compatibility tag does not match the current build, preventing unintended data wipes.
- Progress bars no longer rely on Rich-only options, restoring compatibility with the pinned Rich version in `.venv`.
- MongoDB connection setup is centralized in `mongoctl.create_client`, removing duplicated ensure/ping logic across the CLI.

## [0.2.7] - 2025-11-03
### Added
- `MongoGuard` keeps the managed local MongoDB process alive for the entire daemon lifetime, automatically restarting `mongod` whenever connectivity checks fail.

### Changed
- `python -m wks.daemon` (the launchd entry point) now enforces Mongo availability before monitoring starts and passes the configured URI into the daemon so service start/restart always brings the database online.

## [0.2.6] - 2025-11-01
### Added
- Daemon now launches a background maintenance thread that regularly runs `SimilarityDB.audit_documents()` and shuts down cleanly with the Mongo client.

### Changed
- `wkso service status` and `wkso db info` display timestamps using the configured `display.timestamp_format` and backfill missing byte totals by inspecting on-disk files.

### Fixed
- Space DB audits handle documents stored with plain filesystem paths (without `file://`), ensuring missing `bytes` metadata is repopulated.

## [0.2.5] - 2025-10-29
### Added
- `wkso extract` runs the configured extractor and persists artefacts without touching the database.
- `wkso index --untrack` removes tracked entries and cleans their extraction artefacts from the Space DB.

### Changed
- Space database documents now store absolute file URIs, checksum/size/angle metadata, and all CLI views respect `display.timestamp_format`; `wkso db info` surfaces timestamp, checksum, size, angle, and URI in that order.
- `wkso config print` emits the canonical config structure (including `display` and `mongo` blocks) and normalization defaults; `wkso index` shares the extraction pipeline with `wkso extract`.
- Similarity indexing caches extracted content under `.wkso/<checksum>.md`, cleans stale artefacts on updates/moves, and tracks removals via the CLI.

## [0.2.4] - 2025-10-29
### Added
- `display.timestamp_format` config option (default `%Y-%m-%d %H:%M:%S`) drives all CLI/Obsidian timestamp output.

### Changed
- `wkso db info` now surfaces checksum, chunk count, and size columns and respects the configured timestamp format across both space/time views.

## [0.2.3] - 2025-10-29
### Added
- `wkso --version` now includes the current git SHA (when available) alongside the package version.
- `wkso config print` surfaces the shared `mongo` block and hides legacy `similarity.mongo_*` keys so the output matches the canonical config structure.

### Changed
- Service lifecycle now fully manages the bundled MongoDB: `install|start|reset` auto-start `mongod`, `stop|reset|uninstall` shut it down, and `wkso db reset` restarts it after clearing data so the daemon immediately reconnects.
- CLI database commands (`wkso db info/query/reset`) bootstrap the local Mongo instance before use, preventing connection-refused errors during manual runs.

## [0.2.2] - 2025-10-28
### Added
- `wkso --version` prints the installed CLI version.

### Fixed
- `wkso db query` and related commands now connect with minimal config and respect patched `pymongo.MongoClient`, avoiding hard `similarity.enabled` requirements.

### Changed
- Canonicalized `wkso db info` (dropping the `stats` alias) with short timeouts and defaults for missing config values.
- `wkso service install|start|reset` now verify MongoDB is reachable and auto-start a local `mongod` on the default port when needed.
- All CLI code paths (including `wkso db`) now auto-start the default local MongoDB when it isn't already running.
- Config promotes MongoDB settings to a dedicated `mongo` block; similarity inherits those values automatically.

## [0.2.0] - 2025-10-28
### Added
- Rich dashboard for `wkso service status` with parsed launchctl info and fast Space DB panel.
- `wkso service reset` to stop agent, reset DB/state, and restart cleanly.
- `wkso db reset` to drop Mongo databases and remove local data dir.
- `-n/--latest` to `wkso db info` to list most-recent files/snapshots quickly.
- Auto-start local mongod (27027) during `wkso index` when needed.
- Directory move handling via `rename_folder` to update descendant paths in-place.
- Pytest suite for Space DB (index, move, rename detection, folder moves).

### Changed
- `wkso db info` uses a lightweight client with short timeouts for responsiveness.
- Service status defaults to rich panels; json mode emits the structured status document.
- Docling is now a required extractor (no optional branches).
- Primary CLI is `wkso`; package remains `wks`.

### Removed
- Legacy `analyze` CLI surface; kept CLI minimal: `config`, `service`, `index`, `db`.

## [0.1.1] - 2025-10-28
### Added
- Initial rich status panel, tests setup, KISS/DRY cleanup.

## [0.1.0] - 2025-10-27
- Initial release of `wkso` CLI with `config`, `service`, `index`, `db`.
