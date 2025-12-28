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

## Database Schema
The transform database acts as a localized index of the transform cache.

Collection: `transform`

- `file_uri`: Origin file URI (e.g., `file:///User/docs/invoice.pdf`)
- `engine`: Engine identifier (e.g., `docling`)
- `engine_params_hash`: SHA-256 of the engine configuration used used.
- `output_hash`: SHA-256 of the *content* of the transformed file.
- `data_size`: Size of the transformed output in bytes.
- `last_transform_time`: ISO timestamp.
- `cache_path`: Absolute path to the cached artifact.

## Graph Integration
When a transform is successfully executed (or retrieved from cache), the system MUST update the Knowledge Graph:

1.  **Nodes**: Ensure both the `source_uri` (original file) and `output_uri` (cache file) exist in the `nodes` database.
2.  **Edge**: Create a directed edge from `source_uri` to `output_uri` with type `transform`.
    - This explicitly links the binary source to its text representation.
    - Allows traversal from the original document to its indexable content.

## CLI Interface
Entry: `wksc transform`

### transform
- Command: `wksc transform <engine> [options] <file>`
- Behavior: Transforms the file using the specified engine. Returns hash of the transformed content.
    - **Configuration Overrides**: Any key defined in the engine's `data` configuration block can be overridden via CLI flags.
    - **Scripting**: Use `--raw` to output *only* the checksum to STDOUT, enabling shell variable assignment (e.g., `CS=$(wksc transform default x.pdf --raw)`).
    - **Example**:
        - Config: `{"engines": {"default": {"type": "docling", "data": {"ocr": false}}}}`
        - Command: `wksc transform default document.pdf --ocr true`
        - Result: Runs `default` engine but with `ocr=true`.
- Output: `TransformResultOutput` (or raw string if `--raw`)

### show
- Command: `wksc transform show <checksum>`
- Behavior: Retrieve content for a specific transform hash.

## MCP Interface
- `wksm_transform(engine_name,engine_options,file)`
- `wksm_transform_show(checksum)`
