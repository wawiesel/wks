# Scripts

Use the repo scripts instead of ad hoc commands so local checks match CI.

## Required Before Push

```bash
venv/bin/python scripts/check_format.py --fix
venv/bin/python scripts/check_types.py
venv/bin/python scripts/check_complexity.py
venv/bin/pytest
```

## Focused Test Entrypoints

- `scripts/test_unit.py`
- `scripts/test_integration.py`
- `scripts/test_smoke.py`
- `scripts/test_mutation_api.py`

## Maintenance

- `scripts/update_readme_stats.py`
- `scripts/update_traceability_audit.py`
- `scripts/generate_codebase_visualization.py`

## Rule Tooling

UNO checking lives in `.cursor/rules/scripts/check_python.py`.
