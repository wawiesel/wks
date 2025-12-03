# Search Layer Specification

**Purpose**: Query interface for finding files and content across the knowledge base

**Status**: Future work. The capabilities and interfaces below are planned but not yet implemented.

Multiple search types are supported but the main new search type is through Vespa AI.

**Capabilities**:
- Natural language search across indexed documents
- Semantic similarity search
- Combined weighted search across multiple indices

## Planned MCP Interface (Primary)

- `wksm_search(query, indices, limit)` — Execute search query

## Planned CLI Interface (Secondary)

- `wksc search "machine learning papers"`
- `wksc search "related to project Alpha" --vault-only`
- `wksc search "python functions using asyncio" --index <index_name>`
