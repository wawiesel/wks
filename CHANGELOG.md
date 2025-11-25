# Changelog

All notable changes to this project will be documented in this project will be documented in this file.

The format is based on Keep a Changelog, and this project adheres to Semantic Versioning (SemVer).

## [0.4.0] - 2025-11-24

### Added
- Full diff and transform engine configuration with proper defaults
- Diff engines: myers (text diff with context lines), bsdiff3 (binary diff)
- Transform engines: docling (PDF/DOCX/PPTX to Markdown with OCR, timeout, caching)
- Transform cache system with checksum-based keys (file + engine + options)
- Comprehensive MCP server documentation in SPEC.md and README.md
- MCP usage examples showing installation and available tools

### Fixed
- MCP vault_status tool now uses VaultStatusController (was calling non-existent method)
- All 13 MCP tools verified working via integration tests

### Changed
- Removed obsolete extract, index, and related CLI commands (similarity features under redesign)
- MCP server tools focus on monitor and vault operations only
- Updated README status: MCP server fully functional and documented

### Documentation
- SPEC.md: Added Vault Tools section, removed obsolete tool references, documented architecture
- README.md: Added MCP Server section with installation/usage, tool listing, command examples
- All version numbers updated to 0.4.0

## [0.3.7] - 2025-01-24
### Changed
- Refactored high-complexity functions (daemon.py, config_validator.py, vault.py) for better maintainability (CCN < 15)
- Improved code organization with extracted helper methods
- All tests passing (139 total)

### Fixed
- monitor validate command NameError (undefined monitor_config variable)
- Now properly uses MonitorController.validate_config()

### Removed
- Similarity/related functionality temporarily disabled for redesign
- Deleted obsolete test files (test_cli_related.py, test_similarity_add_file.py, test_space_db.py, test_cli_db_info.py, test_vault_controller.py obsolete tests)
- Removed 1,537 lines of obsolete test code

### Documentation
- Updated README.md with current architecture, quick start guide, and status
- Added status notes to SPEC.md marking similarity features as under redesign
- Comprehensive smoke tests for all wks0 commands

## [0.2.8] - 2025-11-03
### Added
- Every Mongo database now stores a `_wks_meta` compatibility tag so upgrades can reuse existing embeddings when the schema is still compatible. Configure overrides via `mongo.compatibility.space|time` in `~/.wks/config.json`.
- `wks0 db info/query` and the daemon status panel validate compatibility tags and explain how to override them instead of silently rebuilding the database.
- Optional Obsidian views that read `SimilarityDB` (Health/ActiveFiles) honor the same compatibility tags.
- Markdown outputs (service status, `db query`) now render through Jinja2 templates fed by the same JSON payloads used for `--display json`.

### Changed
- `wks0 service`/daemon startup halts early when the stored compatibility tag does not match the current build, preventing unintended data wipes.
- Progress bars no longer rely on Rich-only options, restoring compatibility with the pinned Rich version in `.venv`.
- MongoDB connection setup is centralized in `mongoctl.create_client`, removing duplicated ensure/ping logic across the CLI.
- `wks0 mcp install` registers the MCP server with Cursor, Claude, and Gemini configs so clients can auto-launch it without manual editing.
- The WKS daemon now embeds an MCP broker; `wks0 mcp run` automatically proxies to the running service so Mongo, file monitoring, and MCP live under the same `wks0 service` lifecycle.

## [0.2.7] - 2025-11-03
### Added
- `MongoGuard` keeps the managed local MongoDB process alive for the entire daemon lifetime, automatically restarting `mongod` whenever connectivity checks fail.

### Changed
- `python -m wks.daemon` (the launchd entry point) now enforces Mongo availability before monitoring starts and passes the configured URI into the daemon so service start/restart always brings the database online.

## [0.2.6] - 2025-11-01
### Added
- Daemon now launches a background maintenance thread that regularly runs `SimilarityDB.audit_documents()` and shuts down cleanly with the Mongo client.

### Changed
- `wks0 service status` and `wks0 db info` display timestamps using the configured `display.timestamp_format` and backfill missing byte totals by inspecting on-disk files.

### Fixed
- Space DB audits handle documents stored with plain filesystem paths (without `file://`), ensuring missing `bytes` metadata is repopulated.

## [0.2.5] - 2025-10-29
### Added
- `wks0 extract` runs the configured extractor and persists artefacts without touching the database.
- `wks0 index --untrack` removes tracked entries and cleans their extraction artefacts from the Space DB.

### Changed
- Space database documents now store absolute file URIs, checksum/size/angle metadata, and all CLI views respect `display.timestamp_format`; `wks0 db info` surfaces timestamp, checksum, size, angle, and URI in that order.
- `wks0 config print` emits the canonical config structure (including `display` and `mongo` blocks) and normalization defaults; `wks0 index` shares the extraction pipeline with `wks0 extract`.
- Similarity indexing caches extracted content under `.wkso/<checksum>.md`, cleans stale artefacts on updates/moves, and tracks removals via the CLI.

## [0.2.4] - 2025-10-29
### Added
- `display.timestamp_format` config option (default `%Y-%m-%d %H:%M:%S`) drives all CLI/Obsidian timestamp output.

### Changed
- `wks0 db info` now surfaces checksum, chunk count, and size columns and respects the configured timestamp format across both space/time views.

## [0.2.3] - 2025-10-29
### Added
- `wks0 --version` now includes the current git SHA (when available) alongside the package version.
- `wks0 config print` surfaces the shared `mongo` block and hides legacy `similarity.mongo_*` keys so the output matches the canonical config structure.

### Changed
- Service lifecycle now fully manages the bundled MongoDB: `install|start|reset` auto-start `mongod`, `stop|reset|uninstall` shut it down, and `wks0 db reset` restarts it after clearing data so the daemon immediately reconnects.
- CLI database commands (`wks0 db info/query/reset`) bootstrap the local Mongo instance before use, preventing connection-refused errors during manual runs.

## [0.2.2] - 2025-10-28
### Added
- `wks0 --version` prints the installed CLI version.

### Fixed
- `wks0 db query` and related commands now connect with minimal config and respect patched `pymongo.MongoClient`, avoiding hard `similarity.enabled` requirements.

### Changed
- Canonicalized `wks0 db info` (dropping the `stats` alias) with short timeouts and defaults for missing config values.
- `wks0 service install|start|reset` now verify MongoDB is reachable and auto-start a local `mongod` whenever the configured URI targets loopback.
- All CLI code paths (including `wks0 db`) now auto-start the configured local MongoDB when it isn't already running.
- Config promotes MongoDB settings to a dedicated `mongo` block; similarity inherits those values automatically.

## [0.2.0] - 2025-10-28
### Added
- Rich dashboard for `wks0 service status` with parsed launchctl info and fast Space DB panel.
- `wks0 service reset` to stop agent, reset DB/state, and restart cleanly.
- `wks0 db reset` to drop Mongo databases and remove local data dir.
- `-n/--latest` to `wks0 db info` to list most-recent files/snapshots quickly.
- Auto-start local mongod for any loopback URI during `wks0 index` when needed.
- Directory move handling via `rename_folder` to update descendant paths in-place.
- Pytest suite for Space DB (index, move, rename detection, folder moves).

### Changed
- `wks0 db info` uses a lightweight client with short timeouts for responsiveness.
- Service status defaults to rich panels; json mode emits the structured status document.
- Docling is now a required extractor (no optional branches).
- Primary CLI is `wks0`; package remains `wks`.

### Removed
- Legacy `analyze` CLI surface; kept CLI minimal: `config`, `service`, `index`, `db`.

## [0.1.1] - 2025-10-28
### Added
- Initial rich status panel, tests setup, KISS/DRY cleanup.

## [0.1.0] - 2025-10-27
- Initial release of `wks0` CLI with `config`, `service`, `index`, `db`.
