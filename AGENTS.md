# AGENTS.md — Agent Memory (Internal Only)

This file is the authoritative memory and playbook for the WKS agent. It is for the agent, not end‑users. Keep it up to date with machine‑specific context and decisions. The rest of the repo (README, SPEC, docs/) is for everyone.

## Identity & Mission
- Role: Manage WKS daemon, keep FS ↔ Obsidian (`~/obsidian/WKS`) coherent, minimize noise, prefer offline/local.
- Success: Accurate ActiveFiles, clear FileOperations, safe Docs extracts, helpful routing/suggestions.

## Hard Boundaries
- Write scope: only under `~/obsidian/WKS` (base_dir from config).
- Respect ignore rules: dotfolders except `.wks`, `~/Pictures`, and `monitor.ignore_*` from config.
- Destructive actions (delete/move) are opt‑in, logged, and reversible when possible.

## Environment Snapshot (fill in your machine specifics)
- OS and version: <macOS … / Linux …>
- Python venv path: <…>
- Mongo availability: <installed|not installed>; URI: `mongodb://localhost:27027/`
- LLM availability: `ollama` <installed|not installed>; default model: <…>

## Canonical Config Template (~/.wks/config.json)
```json
{
  "vault_path": "~/obsidian",
  "obsidian": {
    "base_dir": "WKS",
    "log_max_entries": 500,
    "active_files_max_rows": 50,
    "source_max_chars": 60,
    "destination_max_chars": 60,
    "docs_keep": 99,
    "auto_project_notes": false
  },
  "monitor": {
    "include_paths": ["~/2025-WKS"],
    "exclude_paths": [],
    "ignore_dirnames": [".git", "_build"],
    "ignore_globs": ["*.tmp", "~*"],
    "state_file": "~/.wks/monitor_state.json"
  },
  "activity": {
    "state_file": "~/.wks/activity_state.json"
  },
  "similarity": {
    "enabled": false,
    "mongo_uri": "mongodb://localhost:27027/",
    "database": "wks_similarity",
    "collection": "file_embeddings",
    "model": "all-MiniLM-L6-v2",
    "include_extensions": [".md", ".txt", ".pdf", ".docx", ".pptx"],
    "min_chars": 200,
    "max_chars": 200000,
    "chunk_chars": 1500,
    "chunk_overlap": 200,
    "offline": true
  },
  "extract": { "engine": "builtin", "ocr": false, "timeout_secs": 30 },
  "llm": { "model": "gpt-oss:20b" }
}
```

## Operating Principles
- Offline‑first: avoid network; prefer local models and tools.
- Minimal churn: coalesce events, throttle writes (ActiveFiles/Health are throttled in code).
- Traceability: all FS ops recorded to `~/.wks/file_ops.jsonl` → `WKS/FileOperations.md` rebuilt from ledger.
- Forward-only rule: We only move forward. We write new code and toss the old. Every git commit should be a DRY masterpiece.

## Monitored Roots (edit for your setup)
- Prioritized include paths: <add explicit directories>
- Known staging areas: `~/Downloads`, Desktop; routing heuristics: projects → `~/YYYY-Name`, docs → `~/Documents/YYYY_MM-Name`, deadlines → `~/deadlines/YYYY_MM_DD-Name`.

## ActiveFiles Logic
- Source: ActivityTracker events + optional similarity “embedding_changes” window stats.
- Columns: angle; °/hr, °/day, °/wk (from Mongo changes if enabled); last modified; file link.
- Update cadence: on daemon start and roughly every 30 seconds; respects ignore rules.

## Similarity & Extracts (optional)
- When enabled, add/rename/remove updates embeddings and logs “degrees” between embeddings into Mongo `embedding_changes`.
- Extracted text snapshots write to `~/obsidian/WKS/Docs/<checksum>.md` and rotate to keep last N.
- Manual indexing: `wks analyze index <paths...>`; query/route suggestions: `wks analyze query|route`.

## Health & Maintenance
- Health JSON: `~/.wks/health.json`; landing `~/obsidian/WKS/Health.md` refreshed via daemon or `wks analyze health --update`.
- Similarity prune: daemon periodically removes missing/ignored entries from DB.
- Broken symlinks cleanup: vault `_links` helpers in `obsidian.py`.

## Naming & Routing Rules
- Projects: `YYYY-Name`; Documents: `YYYY_MM-Name`; Deadlines: `YYYY_MM_DD-Name`.
- `wks analyze name --path <dir>` suggests Name token; prefer PascalCase or snake_case; single hyphen between date and name.
- Exceptions/overrides: <list any deviations you want enforced>

## Safety & Ignore Rules
- Never touch outside `~/obsidian/WKS` when writing; never modify user content unless acting on monitored events.
- Default ignores: dotsegments (except `.wks`), `~/Pictures`, config `exclude_paths`, `ignore_dirnames`, `ignore_globs`.
- Add extra sensitive paths or patterns here: <…>

## Service Control Cheatsheet
- Start/stop/status: `wks service start|stop|status|restart`
- Logs: `~/.wks/daemon.log`; lock: `~/.wks/daemon.lock`
- macOS: optional launchd agent `~/Library/LaunchAgents/com.wieselquist.wks.plist`

## Daily/Weekly Rituals
- Daily: ensure daemon running; glance `ActiveFiles.md`; route strays; index new content if similarity on.
- Weekly: refresh Desktop links (3–5 projects); run `health --update`; prune stale docs; archive to `_old/YYYY/`.

## Troubleshooting Quick Notes
- ActiveFiles empty → wrong include_paths, ignores too broad, or no recent events; restart service to force rebuild.
- No vault writes → verify `obsidian.base_dir` and `~/obsidian/WKS` exists; check daemon.log.
- Similarity failures → confirm Mongo running or disable/enable `offline`; validate include_extensions.

## Preferences & Heuristics (your calls)
- Suggestion cadence and channels: <how often, where to surface>
- File types to prioritize in ActiveFiles: <exts>
- Thresholds for “active”: <angle cutoffs>

## Current Focus & Priorities
- Top projects: <…>
- Upcoming deadlines: <…>
- Watchlist files: <…>

## Decisions Log
- <YYYY-MM-DD> Decision/context → rationale → outcome

## Scratchpad
- Notes to self, temp rules, experimental toggles.

## Commit Quality Checklist
- DRY: No duplication; extract helpers where appropriate.
- Minimal diff: Change only what the task requires.
- Clear scope: One focused concern per commit.
- Tests or verification: Run the pertinent command(s) to validate behavior.
- Docs touched: Update AGENTS.md/CONTRIBUTING.md only if behavior or usage changed.
- Reversible: Avoid destructive migrations without clear rationale and path back.

## Testing Responsibility (Non‑Negotiable)
- The developer is responsible for end‑to‑end verification before hand‑off. The user’s tests must be a SUPER SIMPLE RERUN of tests we already executed locally.
- Always test with Docling and Mongo running. No “optional” branches. The service is a watcher; core ops must work via CLI alone.
- Global flags precede subcommands (argparse): place `--display rich|basic` before `config|service|index|db`.

## Required Smoke Tests (Space DB)
- Index new file: `wkso --display rich index ~/test/file.txt` → `wkso --display rich db stats -n 5` shows it.
- Re‑index unchanged file: reports skipped; totals stable.
- File move (daemon running): move file → totals unchanged; single logical entry remains (path updated in place).
- Directory move (daemon running): move folder with files → totals unchanged; descendants updated in place.
- Query/stats ergonomics: `wkso --display rich db query --space --filter '{}' --limit 5` and `wkso --display rich db stats -n 5` succeed.

## Foreground Daemon for Local Testing (No Install)
- Start in one terminal:
  - `export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"`
  - `python -m wks.daemon` (Ctrl+C to stop)
- In another terminal, run the smoke tests above; confirm behavior matches.

## Hand‑Off Rule
- Do not ship changes unless the smoke tests above pass locally. If tests require specific setup (Docling/Mongo), state it explicitly and provide copy‑paste commands.

## Obsidian Conventions (imported)
- Pages link knowledge and provide personal context; avoid documenting directory scaffolding or implementation details in the vault.
- Organize around responsibilities, deliverables, organizations, people, and presentations.
- Use tables only where structured overviews help (e.g., meetings, trips); prefer bullets for topic discussions.
- Meetings: one page per series with a year table (e.g., NCSP TPR). Trips: single `Trips.md` page with Upcoming/Past tables, no per‑trip pages.
- Topics: track where/when discussed; bullets not tables. Projects/Organizations/People: standard knowledge graph nodes.

## File Organization Heuristics (imported)
- No loose files; everything lives in directories.
- Projects in home: `~/YYYY-ProjectName/` for active WIP.
- Documents (completed/reference): `~/Documents/YYYY_MM-Name/` or yearly categories as needed.
- Deadlines: `~/deadlines/YYYY_MM_DD-Name/`.
- Events (presentations): one directory per event `YYYY_MM-EventName/`; keep revisions in `_drafts/` within that folder; final(s) live at top level.
- Trips: `~/Documents/YYYY-Trips/YYYY_MM-Location/` containing all materials (presentations, receipts, etc.).
- Archive by project completion year to `~/_old/YYYY/`. Deletion is allowed for temp/duplicates/obsolete items; not all content is archival.

## Anti‑Patterns to Avoid (imported)
1) No “Misc” directories. 2) Avoid generic names (e.g., Software-Tools, Administrative, AI-Research). 3) Don’t document `_drafts/` or revision counts in vault pages. 4) Don’t create separate directories per file revision. 5) Don’t overuse tables. 6) Fix folder‑as‑file artifacts from downloads.

## Project‑Specific Patterns (imported)
- DNCSH (2025-DNCSH): monthly `1.03.01.02 DNCSH FY25 {Month}.pptx`; PMPs `2025-Q{N}-PMPDNCSH_rev*.docx`; status reports → `~/Documents/2025-DNCSH-Status/`.
- NRC (2025-NRC): reviews `00_Overview_SCALE_NRC_TPR_*.pptx`; SOWs `1886-Z720-24 - NRC - SOW *.pdf/docx`; monthly `31310025S0003 *.docx/pdf`.
- SCALE (2025-SCALE): quality `2025_03_SCALE_Quality_Initiatives*.pptx`; validation reports; inputs/outputs `.inp .out .f71 .t16`.

## Migration Notes (imported)
- Stacks → WKS mapping: `stacks/_inbox/` → process/file; `stacks/organizations/` → `~/Documents/` or project dirs; `stacks/records/self/` → `~/Documents/Personal/`; `stacks/records/others/` → `~/Documents/Recommendations/`; `stacks/projects/` → `~/YYYY-Project`.
