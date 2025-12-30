# Transform Specification

## Purpose
The transform layer provides an interface to convert binary or complex documents (PDFs, DOCX, PPTX) into plain text or Markdown. This enables downstream systems (Search, Indexing, AI Agents) to reason about the content of these files.

Key design principles:
- **Config-First**: Engines and cache locations are defined in `config.json`.
- **Persistent Cache**: Transformation is expensive; results are cached on disk.
- **Monitored Cache**: The cache directory itself is typically monitored, allowing transformed artifacts to automatically enter the Knowledge Graph.

## Configuration
- Location: `{WKS_HOME}/config.json`
- Block: `transform`

### Structure
```json
"transform": {
    "cache": {
        "base_dir": "~/_transform",
        "max_size_bytes": 1073741824
    },
    "engines": {
       "dx": {
         "type": "docling",
         "data": {
           "ocr": "none",
           "timeout_secs": 30
         }
       },
       "dx-ocr": {
         "type": "docling",
         "data": {
           "ocr": "tesseract",
           "ocr_languages": "eng,deu",
           "image_export_mode": "referenced",
           "pipeline": "standard",
           "timeout_secs": 60
         }
       }
    }
}
```

### Engine Types vs. Named Engines
WKS defines **Engine Types** (the underlying implementation, e.g., `docling`, `test`).
Users define **Named Engines** in `config.json`.
- Multiple named engines can use the same type (e.g., one for fast/no-ocr, one for high-res).
- The CLI refers to the **Named Engine** (the key in the `engines` dict).

### Docling Engine Options

| Option | Type | Description |
|--------|------|-------------|
| `ocr` | string | `"none"` to disable OCR, or engine name: `"tesseract"`, `"easyocr"` |
| `ocr_languages` | string | Comma-separated languages, e.g., `"eng,deu"` |
| `image_export_mode` | string | `"placeholder"`, `"embedded"`, or `"referenced"` |
| `pipeline` | string | `"standard"` or `"vlm"` |
| `timeout_secs` | int | Timeout in seconds (default 30) |

### Cache Configuration
- `base_dir`: (Required) Path to cache directory. Should be in a monitored directory.
- `max_size_bytes`: (Required) LRU eviction limit in bytes.

## Normative Schema
- Canonical output schema: `docs/specifications/transform_output.schema.json`.
- Implementations MUST validate outputs against this schema.

## Cache-Database Sync Invariant

The transform database is the **sole authority** for the transform cache. This invariant ensures cache and database are always in sync:

1. **Database → Cache**: Every cache file on disk MUST have a corresponding database record. Orphaned cache files are invalid.
2. **Cache → Database**: Every database record MUST point to an existing cache file. Stale records are invalid.
3. **All access through database**: Reading cached content (by checksum) MUST verify the checksum exists in the database first.
4. **Mutations propagate**: Any operation that modifies the database (reset, delete, prune) MUST also delete the corresponding cache files.

**Consequences:**
- `wksc database reset transform` MUST delete all files in the transform cache directory.
- `wksc cat <checksum>` MUST fail if the checksum is not in the database (even if the file exists on disk).
- Cache eviction (LRU) MUST delete both the database record and the cache file atomically.

## Database Schema
The transform database acts as a localized index of the transform cache.

Collection: `transform`

- `file_uri`: Origin file URI (e.g., `file://hostname/User/docs/invoice.pdf`)
- `cache_uri`: Cached file URI (e.g., `file://hostname/path/to/cache.md`)
- `engine`: Named engine identifier (e.g., `dx`)
- `options_hash`: SHA-256 of the engine options used.
- `checksum`: SHA-256 of the transformed content (also the cache filename).
- `size_bytes`: Size of the transformed output in bytes.
- `created_at`: ISO timestamp of original transform.
- `last_accessed`: ISO timestamp of last access.

## Graph Integration
When a transform is successfully executed (or retrieved from cache), the system MUST update the Knowledge Graph:

1.  **Nodes**: Ensure both the `source_uri` (original file) and `output_uri` (cache file) exist in the `nodes` database.
2.  **Edge**: Create a directed edge from `source_uri` to `output_uri` with type `transform`.
    - This explicitly links the binary source to its text representation.
    - Allows traversal from the original document to its indexable content.

### Image References
If the transform produces secondary artifacts (e.g., extracted images via `image_export_mode="referenced"`), these MUST also be integrated into the graph:

1.  **Nodes**: Create nodes for each extracted image in the cache (`file://...`).
2.  **Edges**: Create a directed edge from the **Markdown Output** to each **Image**.
    - Type: `refers_to`
    - Direction: `Markdown -> Image`
    - Chain: `Source --transform--> Markdown --refers_to--> Image`

## Image Handling
When an engine extracts images (e.g. Docling):
1.  **Storage**: Images MUST be stored in the transform cache directory.
2.  **Naming**: Images MUST be named `<checksum>.<ext>` to avoid collisions, just like the primary markdown output.
3.  **References**: Converting the engine's output to use these cache paths is the responsibility of the Engine adapter.
4.  **Export**: When using `--output`, only the primary artifact (Markdown) is copied. Images remain in the cache, and the markdown references them via absolute file URI (or logic appropriate for the user's viewer).

## CLI Interface

### transform
- Command: `wksc transform <engine> <file> [options]`
- No args: `wksc transform` - Lists available engines with supported types
- Engine only: `wksc transform <engine>` - Shows engine info and supported types
- Behavior: Transforms the file using the specified engine. Returns hash of the transformed content.
    - **Configuration Overrides**: Any key defined in the engine's `data` configuration block can be overridden via CLI flags.
    - **Scripting**: Use `--raw` to output *only* the checksum to STDOUT.
    - **Example**: `wksc transform dx document.pdf --ocr true`
- Output: `TransformResultOutput` (or raw string if `--raw`)

### cat (top-level)
- Command: `wksc cat <target> [--engine <engine>]`
- TARGET can be a file path or a checksum (64 hex chars)
- Behavior: Transform file (or retrieve cached content) and print to stdout.
    - File path: Auto-selects engine based on MIME type from `cat.mime_engines` config.
    - Checksum: Retrieves cached content directly.
- Output: Raw content to stdout

## MCP Interface
- `wksm_transform(engine, file)` - Transform a file
