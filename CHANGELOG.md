# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and this project adheres to Semantic Versioning (SemVer).

## [0.2.0] - 2025-10-28
### Added
- Rich dashboard for `wkso service status` with parsed launchctl info and fast Space DB panel.
- `wkso service reset` to stop agent, reset DB/state, and restart cleanly.
- `wkso db reset` to drop Mongo databases and remove local data dir.
- `-n/--latest` to `wkso db stats` to list most-recent files/snapshots quickly.
- Auto-start local mongod (27027) during `wkso index` when needed.
- Directory move handling via `rename_folder` to update descendant paths in-place.
- Pytest suite for Space DB (index, move, rename detection, folder moves).

### Changed
- `wkso db stats` uses a lightweight client with short timeouts for responsiveness.
- Service status defaults to rich panels; basic fallback prints a structured summary.
- Docling is now a required extractor (no optional branches).
- Primary CLI is `wkso`; package remains `wks`.

### Removed
- Legacy `analyze` CLI surface; kept CLI minimal: `config`, `service`, `index`, `db`.

## [0.1.1] - 2025-10-28
### Added
- Initial rich status panel, tests setup, KISS/DRY cleanup.

## [0.1.0] - 2025-10-27
- Initial release of `wkso` CLI with `config`, `service`, `index`, `db`.

