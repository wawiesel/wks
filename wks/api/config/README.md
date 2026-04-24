# Config API

Typed config models load, validate, and persist `WKS_HOME/config.json`.

## Rules

- Required fields must be present.
- Validation happens on load.
- Command outputs use code-defined Pydantic models.
