# Search Layer Specification

**Note**: This specification needs to be updated to align with the principles established in the monitor and database specifications. It should follow the config-first approach (configuration discussed early, database schema discussed later), remove implementation details, and focus on WHAT (interface, behavior, requirements) rather than HOW (implementation details).

**Purpose**: Query interface for finding files and content across the knowledge base

Multiple search types are supported but the main new search type is through Vespa AI.

**Capabilities**:
- Natural language search across indexed documents
- Semantic similarity search
- Combined weighted search across multiple indices

## MCP Interface (Primary)

- `wksm_search(query, indices, limit)` — Execute search query

## CLI Interface (Secondary)

- `wksc search "machine learning papers"`
- `wksc search "related to project Alpha" --vault-only`
- `wksc search "python functions using asyncio" --index <index_name>`
