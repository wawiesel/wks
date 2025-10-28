# WKS Action Items

Use this checklist to track setup, migration, automation, and maintenance. Link items to Obsidian notes where helpful.

## Setup Checklist

- [ ] Create core directories: `~/deadlines/`, `~/Documents/`, `~/obsidian/`
- [ ] Ensure project naming follows `YYYY-ProjectName`
- [ ] Establish Obsidian vault structure: `Projects/`, `People/`, `Topics/`, `Ideas/`, `Organizations/`, `Records/`
- [ ] Add `Index.md` with dashboard sections
- [ ] Create `obsidian/_links/` mirror for symlinks to key files

## Migration Checklist (from Stacks)

- [ ] Extract trip reports to `~/Documents/YYYY_MM-TripName/` and create/link Obsidian notes
- [ ] Move active projects to `~/YYYY-ProjectName/`
- [ ] Relocate old projects into appropriate `_old/YYYY/` archives
- [ ] Move technical notes to Obsidian `Topics/`
- [ ] Move Organizations (ORNL, NRC) notes to `Organizations/`
- [ ] Move science categories (reactor-physics, nuclear-data) to `Topics/`
- [ ] Move personal records to `Records/`
- [ ] Remove `_trunk.node.md`, `_branch.node.md`, `_leaf.node.md` scaffolding
- [ ] Remove obsolete symlinks from Obsidian vault to stacks
- [ ] Document original intent of incomplete scripts in `~/2025-WKS/bin/`

## Staging Areas Cleanup

- [ ] Identify file purpose and project association for Desktop items
- [ ] Route working files to `~/YYYY-ProjectName/`
- [ ] Route reference docs to `~/Documents/YYYY_MM-DocName/`
- [ ] Route time-sensitive items to `~/deadlines/YYYY_MM_DD-Name/`
- [ ] Archive obsolete items to `_old/YYYY/` or delete
- [ ] Create/Link Obsidian notes for tracked items

## Vault Linking and Coherence

- [ ] For each active project: create/update note and link to filesystem directory
- [ ] Add MOCs (Maps of Content) for major areas (SCALE, nuclear data, etc.)
- [ ] Add tags for cross-cutting themes (e.g., `#validation`, `#proposal`, `#publication`)
- [ ] Add Dataview queries: Active projects, upcoming deadlines
- [ ] Verify symlinked files render/refresh correctly (Cmd+R if needed)

## Agent Ops Checklist

- [ ] Monitor filesystem for new project directories and create Project notes
- [ ] Track file movements and update Obsidian links
- [ ] Suggest related content and connections
- [ ] Surface approaching deadlines to Desktop
- [ ] Suggest archiving stale content to `_old/YYYY/`
- [ ] Identify misplaced files and recommend restructuring
- [ ] Maintain `Index.md` dashboard
- [ ] Clean up broken links in vault
- [ ] Surface relevant archived projects and suggest collaborators

## Maintenance Cadence

### Weekly
- [ ] Refresh Desktop symlinks to current focus (3–5 projects, imminent deadlines)
- [ ] Process `~/Downloads/`
- [ ] Update Obsidian `Index.md`
- [ ] Archive completed/obsolete work

### Monthly
- [ ] Review project status and archive stale content
- [ ] Update knowledge connections (Projects ↔ People ↔ Topics)
- [ ] Review and update WKS spec if needed

### Annual
- [ ] Move completed projects to `_old/`
- [ ] Archive old deadlines
- [ ] Consolidate `Documents/`
- [ ] System cleanup and optimization

## Open Questions / Decisions Log

- [ ] Confirm preferred multi-word naming style: `PascalCase` vs `snake_case`
- [ ] Define automation boundaries for the AI agent (what it can change autonomously)
- [ ] Choose Dataview schemas and tags taxonomy
- [ ] Decide on ROADMAP dates and milestones

## Imported Context Tasks (from Vault Context.md)

### Documents Organization
- [x] 9 loose presentation files organized into event directories (2025-10-20)
- [x] Created categorization directories: `2025-Research-Papers/`, `2025-Technical-Figures/`, `2025-Hardware-Datasheets/`, `2025-AI-Generated-Images/`, `2025-Ideas/`, `2025-Templates/`
- [x] Organized and removed Misc directories: `2025-Misc-Documents/` (16), `2025-Misc-PDFs/` (108), `2025-Misc-Images/` (92)
- [x] Fixed generic names: moved/removed `2025-Administrative/`, `2025-AI-Research/`, `2025-GIS-Data/`, `2025-SCALE-Work/`
- [ ] Separate workshop directories: `2025-DNCSH_Workshops/` vs `2025-Workshop_Slides_Collection/`
- [ ] Route receipt photos in `~/Documents/2025-Trips/` into per-trip folders
- [ ] Verify ANS Winter vs DAF trips in 2024_11 categorization

### Downloads Organization
- [x] Downloads cleaned (2025-10-20): DMGs → `~/Documents/2025-Software-Installers/`; SCALE outputs → `~/2025-SCALE/scratch-tests/`; DALL-E images → `~/Documents/2025-AI-Generated-Images/`; scripts/notebooks → `~/2025-SCALE/scratch-tests/`; HALEU drafts → `~/Documents/2025_07-HALEU_Consortium/_drafts/`; SDL bug files → `~/2025-SCALE/bug-tracking/`; installers → `~/2025-SCALE/installers/`; misc → `~/2025-SCALE/scratch-tests/`; personal → `~/Documents/2025-Personal-Records/`
- [x] Downloads directory empty and organized

### Desktop Organization
- [ ] Decide on large screen recordings (keep/delete/archive)
- [ ] Complete desktop/stacks migration to WKS structure

### Pending Clarifications
- [ ] Where to place Slack exports (Reactorium_Slack_Export_2017_2024.zip)?
- [x] ANSWER presentations: Separate meeting from ANS Winter (2025-10-20)

### Deletion Policy and Candidates
- [x] Deleted DMG installers (3.7GB freed, 2025-10-20)
- [ ] Review UUID-named PDF downloads; generic plot images without context; old DALL‑E images; reproducible SCALE scratch files
