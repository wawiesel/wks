# Index Layer Specification

**Purpose**: Maintain searchable indices of file content and structure

Indices are populated based on rules that chain a transform to an embedding scheme to a database. Two main types of embeddings shall be supported:

1. **Document Embeddings** — Operates on documents
2. **Code Embeddings** — Operates on code

An index typically supports both a diff and a search.

Multiple indices are supported but the main type of index is embedding, RAG-type models.

We will also support the BM25 index for simple text search.

## MCP Interface (Primary)

- `wksm_index_list()` — List available indices
- `wksm_index_create(index_name, index_type)` — Create a new index
- `wksm_index_add(index_name, file_path)` — Add a specific file to the index
- `wksm_index_build(index_name)` — Build/rebuild index
- `wksm_index_status(index_name)` — Show index statistics
- `wksm_index_rule_add(index_name, pattern, engine)` — Add indexing rule
- `wksm_index_rule_remove(index_name, pattern)` — Remove indexing rule
- `wksm_index_rule_list(index_name)` — List indexing rules
- `wksm_db_index(index_name)` — Query index database

## CLI Interface (Secondary)

- `wksc index list` — List available indices
- `wksc index create <index_name> <index_type>` — Create a new index
- `wksc index add <index_name> <file>` — Add a specific file to the index
- `wksc index build <index_name>` — Build/rebuild index
- `wksc index status <index_name>` — Show index statistics
- `wksc index rule add <index_name> <pattern> <engine>` — Add indexing rule
- `wksc index rule remove <index_name> <pattern>` — Remove indexing rule
- `wksc index rule list <index_name>` — List indexing rules
- `wksc db index <index_name>` — Query index database
