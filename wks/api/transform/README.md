# Transform Module

Converts binary files to text/markdown with caching.

## Public API

Two commands (the API surface):

| Command | Purpose |
|---------|---------|
| `cmd_transform` | Transform file → returns `StageResult` |
| `cmd_show` | Show transform record → returns `StageResult` |

CLI also exposes `wksc transform cat` as a shortcut (not an API command).

## Architecture

```
cmd_transform ──┐
cmd_show ───────┼─→ _get_controller() ──→ _TransformController
cmd_cat ────────┘              │
                               ↓
                        _TransformConfig
                               │
                    ┌──────────┼──────────┐
                    ↓          ↓          ↓
            _CacheManager  _get_engine  MongoDB
                               │
                    ┌──────────┴──────────┐
                    ↓                     ↓
            _DoclingEngine          _TestEngine
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
Engines declared in `config.json`:
```json
{
  "transform": {
    "engines": {
      "docling": { "type": "docling", "data": {} }
    }
  }
}
```

## Directory Layout

```
transform/
├── cmd_transform.py      # Public
├── cmd_show.py           # Public
├── __init__.py           # Schema exports only
├── _TransformController.py
├── _CacheManager.py
├── _TransformConfig.py
├── _TransformEngine.py
├── _get_controller.py
├── _get_engine_by_type.py
├── _docling/
│   └── _DoclingEngine.py
└── _testengine/
    └── _TestEngine.py
```

## Testing

Per PUTTPUTT: test only through public commands, not `_` modules.
No direct tests on `_` prefixed modules.
