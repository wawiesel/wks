# Monitor API

The monitor package decides what to track and syncs file metadata into the nodes collection.

## Rules

- Include/exclude checks and priority calculation stay deterministic.
- Commands return stable `StageResult` output contracts.
