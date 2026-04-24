# Transform

The transform layer converts source files into cached textual content and keeps cache metadata in sync with the database.

## Responsibilities

- Select a configured engine
- Transform supported documents into cached output
- Reuse valid cached transforms
- Prune stale cache records
- Materialize transformed content through `cat` and related flows

## Rules

- Cache state and database records must stay consistent.
- Missing cache files are treated as stale state and cleaned up.
- Engines are selected explicitly from config.
- Fallback behavior must be deliberate, visible, and engine-specific.

## Current Engine Families

- `textpass`
- `docling`
- `pdftext`
- `route`

## Contracts

- Command wrappers own the `StageResult` contract.
- Shared cache/content logic lives below command wrappers.
- Output models are defined in Python, not external schema files.
