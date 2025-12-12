# Vault Layer Specification

**Note**: This specification needs to be updated to align with the principles established in the monitor and database specifications. It should follow the config-first approach (configuration discussed early, database schema discussed later), remove implementation details, and focus on WHAT (interface, behavior, requirements) rather than HOW (implementation details).

**Goal**: Manage a knowledge vault that links transient priorities to monitored file system resources.

**Database**: `wks.vault`

**URI-First Design**: All links stored as cross-platform URIs. Local filesystem paths derived on-demand from URIs.

## Symlink Naming Convention

The notes within the vault links the knowledge managed contained in the file system. The vault should not have significant knowledge but focus on connecting things. It changes with time and this is managed within git within the repo.
There should be git hooks that are deployed by WKS to help manage snapshots of the vault. For example, we do not commit files until we are sure all the links are healthy. Obsidian is the prototype vault and for any files external to the vault, we create a symlink within the vault so that the files and directories can be treated like internal files to the vault.

External files are mirrored under `_links/<machine>/` to match filesystem structure:
```
_links/
  mbp-2021/
    Users/ww5/Documents/papers/paper.pdf → /Users/ww5/Documents/papers/paper.pdf
    Users/ww5/2025-ProjectName/README.md → /Users/ww5/2025-ProjectName/README.md
```

## Schema

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

## MCP Interface (Primary)

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

## CLI Interface (Secondary)

- `wksc vault status` — summarize the most recent automated scan
- `wksc vault sync` — force immediate vault sync (normally automatic)
- `wksc vault validate` — validate all vault links (check for broken links)
- `wksc vault fix-symlinks` — rebuild _links/<machine>/ from vault DB
- `wksc vault links <path>` — show all links to and from a specific file
- `wksc database vault` — query the underlying collection
