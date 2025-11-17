# Vault Link Management Plan

**Status:** Implementation planning (Phase 3 — Vault layer)<br>
**Focus:** Canonical handling of external files referenced from the vault with a single Mongo database `wks.vault`.

## Context Snapshot

- The Obsidian vault is the single place where links live; filesystem content must stay link-free per the vault policy in `guides/CLAUDE.md:40-44`. Vault notes reference projects, people, and topics with `[[…]]` links while `_links/` hosts symlinks that mirror curated filesystem paths (`guides/CLAUDE.md:120-144`).
- `ObsidianVault` already knows how to mirror files (`link_file` / `_link_rel_for_source`) and to rewrite wiki links when a source path moves or is deleted (`wks/vault/obsidian.py#L410-L520`). The daemon can therefore react to monitor events without guessing how markdown should be edited.
- The spec calls for a dedicated CLI surface (`wks0 vault …`) plus a Mongo collection (`wks_vault.links`) that tracks every edge from a vault note to either another note or an external target (`SPEC.md:260-294`).

## Objectives

1. Treat `_links/` as the canonical view of any filesystem artifact mentioned inside the vault—no absolute `~/2025-…` paths in markdown.
2. Persist every edge in a single collection `wks.vault`, keyed by `(from_note, link_target_uri, link_line_number)` so syncs remain idempotent.
3. Capture embedded artifacts via an `embed_link` pointing to `_external/checksum/<checksum>` (hard link snapshots) or `_external/uri/<path>` (symlinks that follow the source) so vault embeds are stable even when files move.
4. Provide CLI + daemon entry points so link hygiene stays automated (create/update/detect problems) rather than ad-hoc audits.

## External Link Lifecycle

1. **Select a source file** — `wks0 vault link <path>` verifies the path is under one of the managed work roots, computes the `_links/…` destination via `ObsidianVault.link_file`, and records the pairing in Mongo.
2. **Create / refresh the symlink** — `_links` mirrors home-relative structure (or falls back to the filename) so vault links look like `[[ _links/Documents/2025-Archive/file.pdf ]]`. If the user opts to embed, we also create `_external/checksum/<checksum>` (hard link) plus `_external/uri/<path>` (symlink) and store that path in `embed_link`. The command emits a snippet that can be pasted into the relevant note (Projects, Topics, Records, etc.).
3. **Reference in markdown** — Editors insert only `_links/…` wiki links (optionally with aliases / embeds). Direct filesystem `file:///` URLs are banned by policy; HTTP(S) links remain unchanged but are classified as `external_url` in the DB.
4. **Monitor-driven maintenance** — When `wks.monitor` reports a move, the daemon:
   - Updates the symlink (`ObsidianVault.update_link_on_move`).
   - Rewrites any wiki links (`update_vault_links_on_move`).
   - Touches the Mongo records so downstream queries know the new real path + checksum.
5. **Deletion flow** — On delete, the daemon calls `mark_reference_deleted` to annotate notes and sets the link status to `missing_target`. Separate cleanup removes broken symlinks when requested.

## Database Layout (`wks.vault`)

`wks.vault` stores one document per link edge. `_id` is `sha256(from_note + link_target_uri + link_line_number)` so repeated syncs simply upsert.

| Field | Description |
| --- | --- |
| `_id` | Deterministic checksum identifier |
| `from_note` | `vault:///Projects/2025-NRC.md` style URI (note-relative) |
| `link_line_number` / `section` | Optional precision for display |
| `link_target_uri` | Target URI whether internal or external (`vault:///…`, `_links/...`, `https://…`, `file:///…`) |
| `link_type` | `wikilink`, `embed`, `markdown_url`, `legacy_links` |
| `embed_link` | `_external/checksum/<checksum>` for hard-link snapshots and `_external/uri/<path>` for symlinks that follow the real file |
| `resolved_path` | Absolute realpath when `_links/…` resolves to the filesystem |
| `resolved_checksum` | Short checksum for dedupe/health |
| `resolved_priority` | Copy of latest monitor priority (if lookup succeeds) |
| `link_status` | `ok`, `missing_target`, `missing_symlink`, `stale_embed`, etc. |
| `first_seen` / `last_seen` | Sync timestamps |

This single table supplies everything we need: inbound/outbound link queries, health summaries, unused `_links`, and detection of legacy `[[links/...]]` markup.

## Automation Flow

- The daemon owns link ingestion. Every few seconds (configurable via `vault.update_frequency_seconds`) it scans all vault markdown through `ObsidianVault.iter_markdown_files()`, extracts wiki links / embeds / `[text](http)` references, and upserts them into `wks.vault`.
- Each record is keyed by `sha256(from_note + link_target_uri + line_number)` and stored with fields described above plus `first_seen` / `last_seen` timestamps. Links not seen in the current pass are deleted so the DB mirrors the vault exactly.
- Symlink health is assessed during the scan:
  - Missing `_links/...` entry ⇒ `link_status = "missing_symlink"`
  - Symlink present but real file gone ⇒ `link_status = "missing_target"`
  - Legacy `[[links/...]]` references ⇒ `link_status = "legacy_link"`
  - Normal note links / URLs ⇒ `link_status = "ok"`
- Summary metadata (scan duration, notes scanned, accumulated errors) is stored alongside the records (`_id = "__meta__"`), enabling status displays without re-parsing markdown.
- Monitor events still call `update_link_on_move` / `mark_reference_deleted` for immediate correctness, but the canonical truth comes from the background scan + MongoDB.

## Command Surface

Only two user-facing commands are required:

| Command | Purpose |
| --- | --- |
| `wks0 vault status [--json]` | Renders the latest link health snapshot (totals, counts per status, and the top unhealthy links). Uses the same display approach as `monitor status`. |
| `wks0 db vault [--filter …]` | Direct MongoDB access for power users. Mirrors `wks0 db monitor` but points at the vault collection so ad-hoc queries stay easy. |

No manual “link creation” commands remain; the daemon continuously maintains `_links` and the `wks.vault` collection.

## Daemon Responsibilities

1. **On monitor event (move/rename)** — Continue updating `_links` targets and wiki references (`update_link_on_move`, `update_vault_links_on_move`) so the user never sees drift.
2. **On delete** — Insert the 🗑️ callout via `mark_reference_deleted` and let the next scan drop or reclassify the record.
3. **Periodic scan** — At `vault.update_frequency_seconds` cadence the daemon runs the link indexer:
   - Traverse `_links/` for missing symlinks and report them via the DB.
   - Parse markdown for every link type and upsert into `wks.vault`.
   - Store scan metadata (`notes_scanned`, `scan_duration_ms`, `errors`) in the `__meta__` record.

## Implementation Plan

1. **Infrastructure** — Mongo helpers for `wks.vault`, dataclasses for parsed links, CLI parser scaffolding.
2. **Scanner** — Vault markdown iterator that classifies every `[[…]]`, `![[…]]`, and `[text](url)` into the four `target_kind` buckets while capturing line numbers.
3. **Resolver** — `_links` resolution layer that maps wiki targets to absolute paths, checks existence + checksum, and looks up monitor metadata for priority.
4. **Sync & Status Commands** — Implement `vault sync` (idempotent) and `vault status` (summary display) with unit tests that build a temp vault + Mongo stub.
5. **Link Command** — `vault link` front-end that orchestrates symlink creation, DB writes, and snippet generation.
6. **Daemon hooks** — Wire monitor callbacks so link data stays fresh without manual syncs; add health reporting.

Testing follows the strategy outlined in the spec: unit tests for parsing/resolution, integration tests for real vault scans, and CLI smoke tests to ensure display output remains consistent for both CLI and MCP modes.
