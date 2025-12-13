# Scripts Directory

This directory contains utility scripts for development, testing, and quality checks.

## Quality Check Scripts

### `check_format.py`
Runs Ruff formatting and linting checks.

**Usage:**
```bash
./scripts/check_format.py [--fix] [files...]
```

### `check_types.py`
Runs Mypy type checking.

**Usage:**
```bash
./scripts/check_types.py [targets...]
```

### `check_complexity.py`
Runs Lizard code complexity analysis.

**Usage:**
```bash
./scripts/check_complexity.py
```

### `check_python.py`
Checks Python files for UNO rule compliance (One File, One Definition).

**Interface:**
```bash
check_python.py [--filter <filter.py>] <dir>
```

**Arguments:**
- `--filter <filter.py>`: Optional filter script that takes a filename as input and emits either:
  - The filename (if file should be checked)
  - Empty string (if file should be filtered out)

  The filter script must exist outside the `.cursor` directory.

- `<dir>`: Directory to check (defaults to current directory)

**Examples:**
```bash
# Check current directory
.cursor/rules/scripts/check_python.py .

# Check specific directory
.cursor/rules/scripts/check_python.py wks/api

# Check with filter script
.cursor/rules/scripts/check_python.py --filter /path/to/filter.py wks/api
```

**Filter Script Interface:**
The filter script should accept a filename as input (via `sys.argv[1]` or function argument) and output either:
- The filename (if the file should be checked)
- Empty string (if the file should be skipped)

Example filter script:
```python
#!/usr/bin/env python3
import sys

filename = sys.argv[1]
# Skip test files
if filename.endswith("_test.py") or "test_" in filename:
    print("")  # Filtered out
else:
    print(filename)  # Include in check
```

## Test Scripts

### `test_unit.py`
Runs unit tests.

### `test_integration.py`
Runs integration tests.

### `test_smoke.py`
Runs smoke tests.

### `test_mutation_api.py`
Runs mutation testing on the API layer.

## Utility Scripts

### `update_readme_stats.py`
Updates code statistics in README.md.

### `generate_codebase_visualization.py`
Generates visualization of codebase statistics.
