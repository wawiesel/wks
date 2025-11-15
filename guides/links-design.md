# Link Maintenance Design

**Status:** Design phase (Phase 6)
**Prerequisites:** Phase 5 (Related Documents) completion

## Overview

Automated maintenance of wiki links in Obsidian vault to keep references accurate as files move.

## Existing Infrastructure

Already implemented in `wks/obsidian.py`:
- `update_vault_links_on_move(old_path, new_path)` - Rewrites `[[links]]` when files move
- `mark_reference_deleted(path)` - Annotates notes referencing deleted files
- `find_broken_links()` - Finds broken symlinks in `_links/`
- `cleanup_broken_links()` - Removes broken symlinks

## New Commands

### `wks0 links audit`
Comprehensive link health check:
- Scan all markdown files in vault
- Find broken wiki links `[[path/to/file]]`
- Find broken wikilink aliases `[[path|alias]]`
- Find references to deleted files
- Generate report of issues

### `wks0 links fix`
Automated repair:
- Fix references to moved files (using file operations log)
- Update legacy `[[links/...]]` to `[[_links/...]]`
- Remove references to permanently deleted files
- Interactive confirmation mode

### `wks0 links report`
Health dashboard:
- Total links in vault
- Broken link count
- Recently updated links
- Most-linked files
- Orphaned files (no incoming links)

## Implementation Approach

### New CLI Module: `wks/cli_links.py`

```python
def cmd_links_audit(args):
    """Audit all wiki links in vault."""
    # 1. Scan vault markdown files
    # 2. Extract all [[wikilinks]]
    # 3. Verify targets exist
    # 4. Report issues

def cmd_links_fix(args):
    """Fix broken links automatically."""
    # 1. Run audit
    # 2. For each broken link:
    #    - Check file_ops.jsonl for moves
    #    - Suggest/apply fix
    # 3. Confirm with user if interactive

def cmd_links_report(args):
    """Generate link health report."""
    # 1. Count all links
    # 2. Compute statistics
    # 3. Format output
```

### Link Scanner

```python
def scan_vault_links(vault_path: Path) -> List[LinkRef]:
    """Extract all wiki links from vault markdown files."""
    # Parse [[target]] and [[target|alias]]
    # Return list of (source_file, link_text, target_path)
```

### Link Validator

```python
def validate_link(link: LinkRef, vault: ObsidianVault) -> LinkStatus:
    """Check if a link target exists and is accessible."""
    # Return: Valid, Broken, MovedTo(new_path), Deleted
```

## Integration with Daemon

The daemon already updates links on move via:
- `daemon.py:211` - `vault.update_vault_links_on_move(src, dest)`

Enhancement: Add periodic audit task
- Run `links audit` weekly
- Surface issues in Health.md
- Suggest running `links fix`

## Output Examples

### Audit Output
```
Link Audit Report
=================

Scanned: 453 markdown files
Total links: 1,247
Broken links: 12

Issues:
  ~/obsidian/Projects/2025-NRC.md:15
    [[_links/old/path/file.pdf]] → Target not found

  ~/obsidian/Topics/Nuclear_Data.md:42
    [[links/legacy/document.pdf]] → Legacy path (use _links)

Run 'wks0 links fix' to repair automatically.
```

### Fix Output
```
Fixing broken links...

~/obsidian/Projects/2025-NRC.md:15
  [[_links/old/path/file.pdf]]
  → File moved to: ~/Documents/2025-Archive/file.pdf
  Fix: [[_links/Documents/2025-Archive/file.pdf]]
  Apply? [Y/n]

Fixed 8 of 12 issues.
4 require manual review.
```

## Testing Strategy

### Unit Tests
- Link extraction regex
- Link validation logic
- Fix application

### Integration Tests
- Full vault scan
- Repair broken links
- Report generation

### Manual Tests
1. Create test vault with known broken links
2. Run audit - verify all issues found
3. Run fix - verify repairs applied
4. Run report - verify statistics correct

## Design Principles

1. **Non-destructive** - Always confirm before changes
2. **Traceable** - Log all link fixes
3. **Reversible** - Maintain backup of originals
4. **Informative** - Clear explanations of issues
5. **Automated** - Minimize manual intervention
