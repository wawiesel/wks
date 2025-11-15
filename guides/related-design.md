# Related Documents Design

**Status:** Design phase (Phase 5)
**Prerequisites:** Phase 4 (Pattern System) completion

## Overview

Extend `SimilarityDB.find_similar()` to provide a user-facing command for discovering semantically related documents.

## Command Design

```bash
# Basic usage
wks0 related <path>

# With filters
wks0 related paper.pdf --limit 10 --min-similarity 0.7 --type pdf

# JSON output
wks0 related paper.pdf --format json

# Explain why related
wks0 related paper.pdf --explain
```

## Implementation Approach

### Extend Existing Code
Current: `wks/similarity.py:549` has `SimilarityDB.find_similar()`
- Already supports `query_path`, `query_text`, `limit`, `min_similarity`, `mode`
- Returns `List[Tuple[str, float]]` (URI, similarity score)

### New CLI Module: `wks/cli_related.py`

```python
def cmd_related(args):
    """Find semantically similar documents."""
    # 1. Load config and build SimilarityDB
    # 2. Call find_similar() with args
    # 3. Format output (table/json)
    # 4. Optionally explain similarity
```

### Explanation Generation

Add method to `SimilarityDB`:
```python
def explain_similarity(self, src: Path, dst: Path, sim: float) -> str:
    """Generate human-readable explanation of why files are similar."""
    # - Check chunk-level overlaps
    # - Identify common topics (TODO: needs topic extraction)
    # - Simple heuristics based on similarity score
```

## Output Formats

### Table (default)
```
Similar to: ~/Documents/paper.pdf

0.892 - ~/Documents/2025-Research/related_paper.pdf
0.784 - ~/2025-NRC/technical_report.pdf
0.723 - ~/Documents/2024-Conference/presentation.pptx
```

### Explained
```
Similar to: ~/Documents/paper.pdf

0.892 - ~/Documents/2025-Research/related_paper.pdf
       Strong semantic overlap - likely same research area

0.784 - ~/2025-NRC/technical_report.pdf
       Moderate topical similarity - shared technical domain
```

### JSON
```json
[
  {
    "path": "~/Documents/2025-Research/related_paper.pdf",
    "similarity": 0.892
  },
  {
    "path": "~/2025-NRC/technical_report.pdf",
    "similarity": 0.784
  }
]
```

## Future Enhancements

- Chunk-level similarity (show which sections match)
- Topic extraction and labeling
- Temporal filtering (only recent documents)
- Cross-reference with Obsidian vault links
- Suggest creating vault connections

## Reference Implementation

See: `wks/cli.py` around line 2000+ for `db info --reference` pattern to follow.
