# Transform Layer Specification

**Note**: This specification needs to be updated to align with the principles established in the monitor and database specifications. It should follow the config-first approach (configuration discussed early, database schema discussed later), remove implementation details, and focus on WHAT (interface, behavior, requirements) rather than HOW (implementation details).

Converts binary documents (PDF, DOCX, PPTX) to text/markdown for searching, indexing, and comparison.

**Why Transform Exists**:
- Binary documents can't be searched, indexed, or compared as-is
- AI agents need text content to reason about documents
- Text diff tools need text representation to show meaningful changes
- Search/index layers need extracted text content

**Caching**: Transformations are computationally expensive (OCR, layout analysis), so results are cached with LRU eviction.

## Engines

The system is written to support multiple engines. Docling is used as a prototype.

## Database Schema

Collection: `wks.transform`

- `file_uri` — File URI (file:// scheme)
- `checksum` — SHA-256 of original file content
- `size_bytes` — Original file size
- `last_accessed` — ISO timestamp of last cache access
- `created_at` — ISO timestamp of transform creation
- `engine` — Transform engine name (e.g., "docling")
- `options_hash` — Hash of engine options used
- `cache_location` — Path to cached transformed file

## MCP Interface (Primary)

- `wksm_transform(file_path, engine, options)` — Transform a file using a specific engine. Returns checksum.
- `wksm_cat(target)` — Retrieve content. `target` can be a checksum or a file path (auto-transforms if needed).
- `wksm_db_transform()` — Query transform database.

## CLI Interface (Secondary)

- `wksc transform` — Transform a file (e.g., `wksc transform docling file.pdf`)
- `wksc cat` — Retrieve content (e.g., `wksc cat <checksum>` or `wksc cat <file>`)
- `wksc database transform` — Query transform database
