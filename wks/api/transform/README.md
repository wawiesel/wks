# Transform Module

Converts binary files to text/markdown with caching.

## Public API

Single command (the API surface):

| Command | Purpose |
|---------|---------|
| `cmd_engine` | Transform file → returns `StageResult` |

CLI also exposes `wksc cat` (top-level) for direct content output.

### Command Naming Convention

Unlike other domains (e.g. `wksc link check` -> `cmd_check.py`), the transform command is dynamic: `wksc transform <engine>`.
The file is named `cmd_engine.py` because the command dispatches to a specific **engine**.

## Architecture

```
cmd_engine ──→ _get_controller() ──→ _TransformController
                          │
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
      "dx": { "type": "docling", "data": {} }
    }
  }
}
```

## Directory Layout

```
transform/
├── cmd_engine.py      # Public
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
