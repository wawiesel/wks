# Search Specification

## Purpose
Query interface for finding files and content across indexed documents. Supports both lexical (BM25) and semantic (embedding-based) search modes, selected automatically based on index configuration.

## Configuration
- Search uses the index configuration (`index` block in `config.json`).
- Search mode is determined by the target index:
  - Index with `embedding_model` configured: semantic search.
  - Index without `embedding_model`: lexical (BM25) search.
- Search strategies combine results from multiple indexes using Reciprocal Rank Fusion (RRF).

## Search Modes

### Lexical (BM25)
- Tokenizes query and indexed chunks.
- Scores using BM25 ranking.
- Returns top-k hits sorted by score.
- Does not support `query_image`.

### Semantic
- Embeds query text (and optionally query image) using the index's embedding model.
- Scores using cosine similarity against stored embeddings.
- Returns top-k hits sorted by similarity.
- Supports `query_image` parameter for multimodal search.

## Search Strategies

Strategies combine results from multiple indexes using Reciprocal Rank Fusion (RRF).

- RRF formula: `score(doc) = Σ 1/(k + rank_i)` where `k=60` and `rank_i` is the rank in result list `i`.
- Each index in the strategy is queried with `k * 3` results (over-fetch for better fusion).
- Results are deduplicated by URI + content hash after merging.
- `search_mode` is `"combined"` and `embedding_model` is `null` for strategy results.

### Resolution order
1. `--strategy <name>`: use named strategy.
2. `--index <name>`: query single index.
3. Neither: use `default_strategy` if set, else `default_index`.
4. Both `--index` and `--strategy`: error.

## Hit Deduplication
- Hits are deduplicated by canonical URI and content hash.
- After deduplication, results are backfilled from ranked candidates to satisfy the requested `k`.

## CLI

- Entry: `wksc search`
- Output formats: `--display yaml` (default) or `--display json`

### search
- Command: `wksc search <query> [--index <name>] [--strategy <name>] [--top N] [--query-image <path>]`
- Behavior: Search the specified index, strategy, or default for documents matching the query.
- `--strategy`: Named search strategy combining multiple indexes.
- `--query-image`: Path to an image file for multimodal semantic search. Rejected for lexical indexes.
- `--top`: Number of results to return (default: 5).
- Output schema: `SearchOutput` with fields: `errors`, `warnings`, `query`, `index_name`, `search_mode`, `embedding_model`, `hits`, `total_chunks`.

## MCP Interface

| Tool | Description |
|------|-------------|
| `wksm_search(query?, index?, k?, query_image?, strategy?)` | Search indexed documents |

- Output format: JSON.
- CLI and MCP MUST return the same data and structure for equivalent calls.

## Error Semantics
- Searching an unconfigured or nonexistent index MUST fail with a schema-conformant error.
- `query_image` on a lexical index MUST fail.
- Empty query on a lexical index MUST fail (query is required for BM25).
- All outputs MUST validate against their schemas before returning to CLI or MCP.

## Formal Requirements
- SRCH.1 — Search mode is determined by index configuration (embedding_model present → semantic, absent → lexical).
- SRCH.2 — Lexical search rejects `query_image`; semantic search accepts it.
- SRCH.3 — Hits are deduplicated by URI and content hash before returning.
- SRCH.4 — CLI/MCP parity: same data and structure for equivalent commands.
- SRCH.5 — Strategy search queries each index in the strategy, merges with RRF, and deduplicates.
- SRCH.6 — `--index` and `--strategy` are mutually exclusive; specifying both is an error.
- SRCH.7 — When neither `--index` nor `--strategy` is given, `default_strategy` is used if set, else `default_index`.
