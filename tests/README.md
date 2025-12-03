# Test Organization

This directory follows a 3-tier test organization strategy:

1. **Smoke Tests** (`tests/smoke/`) - Quick sanity checks that verify basic functionality
2. **Unit Tests** (`tests/unit/`) - Isolated function tests with mocks
3. **Integration Tests** (`tests/integration/`) - Cross-component tests

## Running Tests

### Run all tests
```bash
pytest
```

### Run by tier
```bash
# Smoke tests (fastest, run first)
pytest tests/smoke/ -v

# Unit tests
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v
```

### Run by marker
```bash
# Run smoke tests
pytest -m smoke

# Run unit tests
pytest -m unit

# Run integration tests
pytest -m integration

# Exclude slow tests
pytest -m "not slow"
```

## Naming Conventions

- Test files: `test_*.py`
- Test functions: `test_*`
- Test classes: `Test*`

## Marker Auto-Application

Markers are automatically applied based on directory location:
- Files in `tests/smoke/` → `@pytest.mark.smoke`
- Files in `tests/unit/` → `@pytest.mark.unit`
- Files in `tests/integration/` → `@pytest.mark.integration`

You can also manually apply markers in test files if needed.

## Test Execution Order

Tests should be run in this order:
1. Smoke tests first (quick validation)
2. Unit tests second (isolated component testing)
3. Integration tests last (end-to-end validation)
