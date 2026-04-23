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
    "default_engine": "default",
    "engines": {
       "default": {
         "type": "route",
         "data": {
           "order": ["dx", "ast"],
           "passthrough_text": true,
           "reject_binary": true
         }
       },
       "dx": {
         "type": "docling",
         "data": {
            "ocr": "none",
            "ocr_languages": ["eng"],
           "image_export_mode": "referenced",
           "pipeline": "standard",
           "timeout_secs": 30,
           "to": "md"
         },
         "supported_types": [".pdf", ".docx", ".pptx", ".xlsx", ".doc", ".ppt", ".xls"]
       },
       "pdftext": {
         "type": "pdftext",
         "data": {},
         "supported_types": [".pdf"]
       },
       "ast": {
         "type": "treesitter",
         "data": {
           "language": "auto",
           "format": "sexp"
         },
         "supported_types": [
           ".py", ".js", ".jsx", ".ts", ".tsx", ".c", ".h", ".cpp", ".hpp",
           ".cc", ".java", ".rb", ".go", ".rs", ".php", ".sh", ".bash"
         ]
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
WKS defines **Engine Types** (the underlying implementation, e.g., `docling`, `pdftext`, `test`).
Users define **Named Engines** in `config.json`.
- Multiple named engines can use the same type (e.g., one for fast/no-ocr, one for high-res).
- The CLI refers to the **Named Engine** (the key in the `engines` dict).
- `transform.default_engine` MUST reference one configured named engine.
- `route` is a first-class engine type for explicit dispatch.
- `auto` is not a legal named engine and MUST NOT be used directly.

### Route Engine

`route` is the supported replacement for hidden auto-routing behavior.

- `route.data.order` MUST be an ordered list of configured named engines.
- WKS MUST probe ordered engines in sequence and select the first engine that can honestly handle the file.
- When an ordered engine defines `supported_types`, that filter MUST be authoritative.
- When an ordered engine omits `supported_types`, the engine's own strict applicability rules MUST be used.
- `route` MUST NOT define `supported_types`.
- `route` MUST NOT reference another `route` engine.
- `route` MUST NOT reference a `null` engine in `order`; binary rejection is handled by route policy.
- If no ordered engine matches and `passthrough_text` is true, UTF-8 text MUST use built-in pass-through semantics.
- If no ordered engine matches and `reject_binary` is true, non-text/binary files MUST fail with clear null-transform semantics.
- A route with no ordered engines and no fallback policy is invalid.

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

### Supported Types
- `supported_types` is optional per named engine.
- When present, it is authoritative.
- Direct transform requests MUST fail fast when the file type is unsupported.
- Index auto-indexing MUST skip indexes whose configured engine does not support the file.
- `route` MUST NOT use `supported_types`.

### Null and Pass-Through Semantics
- `null` means no transform can be produced. The caller MUST receive a clear failure.
- `textpass` and `binarypass` are pass-through transforms. The cached artifact is effectively the input content unchanged.
- `route` MAY use built-in text pass-through or binary rejection without requiring named `textpass` or `null` helper engines.

### PDFText Engine Options

| Option | Type | Description |
|--------|------|-------------|
| `timeout_secs` | int | Optional timeout in seconds for the `pdftotext` subprocess |

## Normative Schema
- Canonical output schema: `qa/specs/transform_output.schema.json`.
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
- Command: `wksc transform [--engine <engine>] <file> [options]`
- No args: `wksc transform` - Lists available engines and route policies
- Engine only: `wksc transform --engine <engine>` - Shows engine info; route engines show order/fallback policy and leaf engines show supported types
- Behavior: Transforms the file using the specified engine. If `--engine` is omitted, uses `transform.default_engine`. Returns hash of the transformed content.
    - **Configuration Overrides**: Any key defined in the engine's `data` configuration block can be overridden via CLI flags.
    - **Scripting**: Use `--raw` to output *only* the checksum to STDOUT.
    - **Example**: `wksc transform --engine dx document.pdf --ocr true`
- Output: `TransformResultOutput` (or raw string if `--raw`)

The legacy positional form `wksc transform <engine> <file>` is retired and MUST fail clearly.

### cat (top-level)
- Command: `wksc cat <target> [--engine <engine>]`
- TARGET can be a file path or a checksum (64 hex chars)
- Behavior: Transform file (or retrieve cached content) and print to stdout.
    - File path: Auto-selects engine based on MIME type from `cat.mime_engines` config.
    - Checksum: Retrieves cached content directly.
- Output: Raw content to stdout

## MCP Interface

| Tool | Description |
|------|-------------|
| `wksm_transform_engine(engine, uri, overrides, output?)` | Transform a file using the named engine |
| `wksm_transform_list()` | List available transform engines |
| `wksm_transform_info(engine)` | Show engine info and supported types |

- Output format: JSON.
- CLI and MCP MUST return the same data and structure for equivalent calls.
