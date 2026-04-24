# Config

WKS uses one validated JSON config file at `WKS_HOME/config.json`.

## Rules

- Every required section and required field must be present.
- Validation happens at load time through typed config models.
- Missing or malformed configuration fails immediately.
- Code must not invent defaults for required values.

## Current Structure

The live config covers these domains:

- `monitor`
- `database`
- `service`
- `daemon`
- `vault`
- `log`
- `transform`
- `cat`
- `index` when search/index features are enabled
- `similar` when similarity search is enabled

## Requirements

- Config access is centralized through typed models, not ad hoc dict reads.
- CLI, MCP, REST, and Python services all consume the same config.
- Output from config commands uses code-defined Pydantic models.
