# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and this project adheres to Semantic Versioning (SemVer).

# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and this project adheres to Semantic Versioning (SemVer).

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
