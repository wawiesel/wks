# Index Specification

## Purpose
Maintain searchable indices of file content. Transforms documents, chunks content, and stores chunks in the index database. Optionally builds semantic embeddings for vector search.

## Configuration
- Location: `{WKS_HOME}/config.json`
- Block: `index`

### Structure
```json
"index": {
    "default_index": "main",
    "indexes": {
        "main": {
            "engine": "textpass",
            "embedding_model": "model-name"
        }
    }
}
```

### Fields
- `default_index`: Name of the default index used when none is specified.
- `indexes`: Map of index name to index configuration.
  - `engine`: Transform engine name for content extraction (e.g., `textpass`).
  - `embedding_model`: (Optional) Model name for semantic embeddings. Required for semantic search and `embed` command.

## Database Schema

Collection: `index`
- `uri`: Source file URI
- `index_name`: Name of the index
- `chunk_index`: Ordinal position of chunk within document
- `text`: Chunk text content
- `tokens`: Token count for the chunk
- `checksum`: SHA-256 of original file content

Collection: `index_embeddings`
- `uri`: Source file URI
- `index_name`: Name of the index
- `chunk_index`: Chunk ordinal
- `embedding`: Float vector from embedding model

## CLI

- Entry: `wksc index`
- Output formats: `--display yaml` (default) or `--display json`

### add
- Command: `wksc index add <name> <uri>`
- Behavior: Transform the file, chunk the content, and store chunks in the named index. If an embedding model is configured, also builds embeddings.
- Output schema: `IndexOutput` with fields: `errors`, `warnings`, `uri`, `index_name`, `chunk_count`, `checksum`.

### status
- Command: `wksc index status [name]`
- Behavior: Show statistics for a named index, or all indexes if no name given. Reports document count, chunk count, and URI list per index.
- Output schema: `IndexStatusOutput` with fields: `errors`, `warnings`, `indexes`.

### embed
- Command: `wksc index embed [name] [--batch-size N]`
- Behavior: Build semantic embeddings for all chunks in the named index (or default index). Requires `embedding_model` to be configured.
- Output schema: `IndexEmbedOutput` with fields: `errors`, `warnings`, `index_name`, `chunks_embedded`, `embedding_model`.

## MCP Interface

| Tool | Description |
|------|-------------|
| `wksm_index(name, uri)` | Add a document to an index |
| `wksm_index_status(name?)` | Show index statistics |
| `wksm_index_embed(name?, batch_size?)` | Build embeddings for index |
| `wksm_index_auto(uri)` | Auto-index into all matching indexes |

- Output format: JSON.
- CLI and MCP MUST return the same data and structure for equivalent calls.

## Auto-Index

The `auto` command indexes a URI into all configured indexes where the file type is supported by the index engine. Used by the daemon for automatic indexing of newly monitored files.

- Skips files in the transform cache directory.
- Checks file type support per engine via `_is_supported_for_engine()`.
- Returns lists of indexed and skipped index names.

## Error Semantics
- Missing or unconfigured index MUST fail with a schema-conformant error.
- `embed` on an index without `embedding_model` MUST fail.
- All outputs MUST validate against their schemas before returning to CLI or MCP.

## Formal Requirements
- IDX.1 — `wksc index add` transforms, chunks, and stores content in the named index.
- IDX.2 — `wksc index status` reports document count, chunk count, and URIs per index.
- IDX.3 — `wksc index embed` builds embeddings; requires `embedding_model` in config.
- IDX.4 — Auto-index respects engine file type support and skips transform cache files.
- IDX.5 — CLI/MCP parity: same data and structure for equivalent commands.
