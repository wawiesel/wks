# Agent 1: Smoke Tests & Directory Structure

## Your Mission

Set up the test directory structure and pytest configuration for the 3-tier test organization.

## Tasks

### 1. Create Directory Structure
```bash
mkdir -p tests/unit tests/integration
touch tests/unit/__init__.py tests/integration/__init__.py
```

### 2. Create pytest.ini
Create `tests/pytest.ini` (or update root `pytest.ini`):
```ini
[pytest]
markers =
    smoke: Quick sanity checks - run first
    unit: Isolated function tests with mocks - run second
    integration: Cross-component tests - run last
    slow: Tests that take >1 second

testpaths = tests
python_files = test_*.py
python_functions = test_*
```

### 3. Create tests/README.md
Document the test organization, how to run each tier, and naming conventions.

### 4. Update conftest.py
Add shared fixtures and marker auto-application based on directory:
```python
def pytest_collection_modifyitems(config, items):
    for item in items:
        if "/smoke/" in str(item.fspath):
            item.add_marker(pytest.mark.smoke)
        elif "/unit/" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "/integration/" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
```

### 5. Verify Smoke Tests Pass
```bash
pytest tests/smoke/ -v
```

## Success Criteria

- [ ] `tests/unit/` directory exists with `__init__.py`
- [ ] `tests/integration/` directory exists with `__init__.py`
- [ ] `pytest.ini` has markers configured
- [ ] `tests/README.md` documents the structure
- [ ] `pytest tests/smoke/ -v` passes
- [ ] `pytest --markers` shows smoke, unit, integration markers

## Do NOT

- Move any test files (Agent 2 and 3 will do this)
- Modify existing tests
- Touch daemon or vault test files

