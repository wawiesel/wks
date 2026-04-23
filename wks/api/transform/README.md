# Transform Module

Converts binary files to text/markdown with caching.

## Public API

Single command (the API surface):

| Command | Purpose |
|---------|---------|
| `cmd_engine` | Transform file → returns `StageResult` |

CLI also exposes `wksc cat` (top-level) for direct content output.

### Command Naming Convention

Unlike other domains (e.g. `wksc link check` -> `cmd_check.py`), the transform command is dynamic at runtime:
- `wksc transform <file>` uses `transform.default_engine`
- `wksc transform -e <engine> <file>` uses an explicit configured engine

The file is named `cmd_engine.py` because the command ultimately dispatches to a specific **configured engine**.

## Architecture

```
cmd_engine ──→ _get_controller() ──→ _TransformController
                          │
                          ↓
                   _TransformConfig
                          │
               ┌──────────┼──────────┐
               ↓          ↓          ↓
       _CacheManager  _resolve_engine_selection  MongoDB
                          │
               ┌──────────┴──────────┐
               ↓                     ↓
       _DoclingEngine          _TextPassEngine
```

## Core Concepts

### Cache Key
Composite hash: `SHA256(file) + engine + SHA256(options)`
- File OR config change invalidates cache

### Engine Interface
`_TransformEngine` defines:
- `transform(input, output, options)` - Execute transform
- `get_extension(options)` - Output file extension
- `compute_options_hash(options)` - For cache key

### Config-Driven
Engines are declared in `config.json`, and one named engine is selected as the default:
```json
{
  "transform": {
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
      "ast": {
        "type": "treesitter",
        "data": { "language": "auto", "format": "sexp" },
        "supported_types": [
          ".py", ".js", ".jsx", ".ts", ".tsx", ".c", ".h", ".cpp", ".hpp",
          ".cc", ".java", ".rb", ".go", ".rs", ".php", ".sh", ".bash"
        ]
      }
    }
  }
}
```

`transform.default_engine` is required. `wksc transform <file>` uses that named engine,
and `wksc transform -e <engine> <file>` selects a different configured engine explicitly.

### Route Engine

The `route` engine type is the explicit replacement for hidden transform auto-routing.

`route.data.order` is an ordered list of configured named engines. WKS probes them in order
and picks the first engine that can honestly handle the file.

- If an ordered engine defines `supported_types`, that filter is authoritative.
- If it omits `supported_types`, the engine's native strict behavior decides applicability.
  - `docling` matches document-like inputs.
  - `treesitter` matches files whose configured or inferred language is valid.
  - `imagetext` matches supported image files.
  - `textpass` matches UTF-8 text.
  - `binarypass` matches non-text/binary files.

If no ordered engine matches:
- `passthrough_text: true` uses built-in text pass-through semantics for UTF-8 text.
- `reject_binary: true` uses built-in null semantics for non-text/binary files.

This keeps routing explicit in configuration without requiring fake helper engines just to
say "leave text alone" or "reject binary clearly."

Hidden transform-engine magic is not allowed: `auto` is not a named engine and cannot be
passed directly on the CLI or through config.

### Null and Pass-Through Semantics

- `null` means no transform is available and the caller gets a clear failure.
- `textpass` and `binarypass` are pass-through transforms:
  - the content is preserved
  - the transform is effectively identity
  - the cache still records the result as a transform artifact
- `supported_types` is authoritative:
  - direct transform requests fail fast when the file type is unsupported
  - auto-index skips indexes whose configured engine does not support the file
- `route` does not define `supported_types`:
  - route policy is `order` + `passthrough_text` + `reject_binary`
  - ordered engines own their own type filtering

### Tree-sitter Engine Options

The `treesitter` transform engine accepts the following options under `data`:

- `language`: Required. Use `"auto"` to infer from MIME/extension (see `transform/mime.py`) or set a specific tree-sitter grammar name.
- `format`: Output representation. `"sexp"` (S-expression) is the default and currently the only supported format; sets the `.sexp` extension.

## Directory Layout

```
transform/
├── cmd_engine.py      # Public
├── __init__.py           # Schema exports only
├── _TransformController.py
├── _CacheManager.py
├── TransformConfig.py
├── _TransformEngine.py
├── _RouteEngineConfig.py
├── _get_controller.py
├── _get_engine_by_type.py
├── _docling/
│   └── _DoclingEngine.py
├── _NullEngine.py
├── _resolve_engine_selection.py
├── _supports_file.py
├── _treesitter/
│   └── _TreeSitterEngine.py
├── _textpass/
│   └── _TextPassEngine.py
└── _binarypass/
    └── _BinaryPassEngine.py
```

## Testing

Per PUTTPUTT: test only through public commands, not `_` modules.
No direct tests on `_` prefixed modules.
