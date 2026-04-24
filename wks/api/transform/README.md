# Transform API

The transform package owns engine selection, cache coordination, and transformed-content retrieval.

## Rules

- Command wrappers return `StageResult`.
- Shared transform/cache logic lives below those wrappers.
- Cache files and database records must stay consistent.
