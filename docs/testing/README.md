# WKS Testing Process

This directory contains documentation for WKS's comprehensive testing framework and processes.

## Overview

WKS maintains multiple levels of automated testing to ensure code quality, reliability, and correctness. Our testing strategy includes unit tests, integration tests, smoke tests, mutation testing, and continuous integration checks.

## Quick Reference

- **Run all tests**: `pytest tests/`
- **Run specific test level**:
  - Smoke: `./scripts/test_smoke.py`
  - Unit: `./scripts/test_unit.py`
  - Integration: `./scripts/test_integration.py`
- **Run mutation tests**: `./scripts/test_mutation_api.py`
- **Quality checks**: `./scripts/check_quality.py [--fix]`

## Test Levels

### Smoke Tests (`tests/smoke/`)

**Purpose**: Quick, high-level sanity checks that verify basic system functionality.

**Characteristics**:
- Should complete in < 15 seconds
- Test critical user paths end-to-end
- First line of defense in CI pipeline (fail-fast)
- No external dependencies (uses mongomock)

**When to run**:
- Before committing code
- First stage of CI pipeline
- After any major refactoring

**Example smoke tests**:
- `test_smoke_cli.py`: Verify CLI commands execute without crashing
- `test_smoke_mcp.py`: Verify MCP server can start and respond
- `test_smoke_config.py`: Verify configuration loading and validation

### Unit Tests (`tests/unit/`)

**Purpose**: Isolated tests for individual functions, classes, and modules.

**Characteristics**:
- Test single units of code in isolation
- Mock external dependencies
- Fast execution (< 100ms per test typically)
- High coverage of edge cases and error conditions

**Organization** (mirrors source structure):
```
tests/unit/
├── monitor/          # Monitor layer tests
├── vault/            # Vault layer tests
├── transform/        # Transform layer tests
├── diff/             # Diff layer tests
├── cli/              # CLI interface tests
├── mcp/              # MCP server tests
└── utils/            # Utility function tests
```

**Best practices**:
- One test file per source file
- Use descriptive test names: `test_<function>_<scenario>_<expected_result>`
- Mock external dependencies (database, filesystem, APIs)
- Test both success and failure paths

### Integration Tests (`tests/integration/`)

**Purpose**: Verify interactions between components and with external systems.

**Characteristics**:
- Test component interactions
- Use real external dependencies (MongoDB, filesystem)
- Slower execution (up to several seconds per test)
- Verify end-to-end workflows

**Key integration tests**:
- `test_daemon_monitor_integration.py`: Daemon filesystem monitoring with MongoDB
- `test_vault_persistence.py`: Vault link tracking with real database
- `test_linux_service_install.py`: Service installation in systemd container

**Requirements**:
- MongoDB must be installed (`mongod` binary available)
- Tests start their own MongoDB instances on unique ports
- Some tests require Docker (e.g., service installation tests)

### Mutation Testing

**Purpose**: Test the quality of our test suite by introducing bugs and verifying tests catch them.

**How it works**:
1. `mutmut` modifies source code (e.g., `x + 1` → `x - 1`)
2. Test suite runs against the mutant
3. If tests fail, the mutant is "killed" (good!)
4. If tests pass, the mutant "survived" (bad - test gap!)

**Run mutation tests**:
```bash
./scripts/test_mutation_api.py
```

**Configuration**: `setup.cfg` under `[mutmut]`
- Targets: `wks/api` (excludes CLI/MCP layers)
- Minimum kill rate: 90% (enforced in CI)
- Reports saved to `.mutmut-cache`

**Interpreting results**:
- **91.6% mutation score**: 91.6% of mutations killed by tests
- **Survived mutants**: Indicate test coverage gaps
- Target: ≥90% kill rate

## CI/CD Testing Pipeline

Our GitHub Actions workflow runs tests in three stages:

### Stage 1: Smoke Tests (Fast Fail)
- Runs in pre-built Docker container
- Completes in ~30 seconds
- If any fail, pipeline stops immediately

### Stage 2a: Code Quality (Parallel)
- Formatting check (ruff format)
- Linting (ruff check)
- Type checking (mypy)

### Stage 2b: Docker Deep Tests (Parallel)
- Full test suite with coverage
- Mutation testing
- Linux service installation tests
- Stats generation and README updates

### Stage 3: Python Version Compatibility (Parallel)
- Tests on Python 3.10, 3.11, 3.12
- Verifies code works across supported versions
- Runs after smoke tests pass

See [ci-runner.md](ci-runner.md) for details on the Docker testing infrastructure.

## Local Development Workflow

### Pre-commit Hooks

We use `pre-commit` to run checks automatically:

**Install hooks**:
```bash
pre-commit install --hook-type pre-commit --hook-type pre-push
```

**Pre-commit checks** (before commit):
- Trailing whitespace removal
- EOF fixer
- YAML syntax check
- Large file detection
- Ruff formatting and linting
- Mypy type checking

**Pre-push checks** (before push):
- Full test suite (`pytest`)
- Code complexity analysis (`lizard`)

**Manual run**:
```bash
pre-commit run --all-files
```

### Running Tests Locally

**Full test suite**:
```bash
pytest tests/ -v --tb=short
```

**With coverage**:
```bash
pytest tests/ --cov=wks --cov-report=html --cov-report=term
open htmlcov/index.html
```

**Parallel execution** (faster):
```bash
pytest tests/ -n auto  # Uses all CPU cores
```

**Specific test file**:
```bash
pytest tests/unit/monitor/test_controller.py -v
```

**Specific test function**:
```bash
pytest tests/unit/monitor/test_controller.py::test_get_status_success -v
```

**Integration tests only** (requires MongoDB):
```bash
pytest tests/integration/ -v
```

**With debugging**:
```bash
pytest tests/ -v --tb=long --pdb  # Drop into debugger on failure
```

## Test Requirements

### System Dependencies

**MongoDB**:
- Required for integration tests
- Tests start their own `mongod` instances
- Must have `mongod` binary in PATH

Install on macOS:
```bash
brew install mongodb-community
```

Install on Ubuntu:
```bash
# See integration test files for GPG key setup
sudo apt-get install -y mongodb-org-server
```

**Docker**:
- Required for service installation tests
- Must have Docker daemon running

### Python Dependencies

All testing dependencies are in `pyproject.toml`:
- `pytest`: Test framework
- `pytest-cov`: Coverage reporting
- `pytest-xdist`: Parallel test execution
- `pytest-timeout`: Test timeouts
- `mongomock`: In-memory MongoDB for unit tests
- `mutmut`: Mutation testing
- `coverage`: Coverage analysis

Installed automatically with:
```bash
pip install -e .
```

## Writing Tests

### Test Structure

```python
"""Test module docstring explaining what's being tested."""

import pytest
from wks.monitor.controller import MonitorController

def test_monitor_status_success():
    """Test that status returns correctly under normal conditions."""
    # Arrange
    controller = MonitorController(config)

    # Act
    status = controller.get_status()

    # Assert
    assert status.running is True
    assert status.file_count > 0

def test_monitor_status_not_running():
    """Test status when monitor is not running."""
    # Arrange
    controller = MonitorController(config)
    controller.stop()

    # Act
    status = controller.get_status()

    # Assert
    assert status.running is False
```

### Fixtures

**Shared fixtures** in `tests/conftest.py`:
- `tmp_path`: Temporary directory (pytest builtin)
- `minimal_config_dict()`: Minimal WKS config
- `run_cmd()`: Helper for testing CLI commands

**Custom fixtures**:
```python
@pytest.fixture
def mongo_wks_env(tmp_path, monkeypatch):
    """Set up temporary WKS environment with MongoDB."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()

    config = WKSConfig.model_validate(minimal_config_dict())
    config.save()

    monkeypatch.setenv("WKS_HOME", str(wks_home))

    yield {"wks_home": wks_home, "config": config}
```

### Test Markers

Mark tests with pytest markers for selective execution:

```python
@pytest.mark.integration
def test_real_mongodb():
    """This test requires real MongoDB."""
    pass

@pytest.mark.mongo
def test_with_mongodb():
    """This test uses MongoDB."""
    pass

@pytest.mark.slow
def test_long_running():
    """This test takes > 1 second."""
    pass
```

Run only marked tests:
```bash
pytest -m integration  # Integration tests only
pytest -m "not slow"   # Skip slow tests
```

## Troubleshooting

### Tests Fail with "mongod not found"

Integration tests require MongoDB.

**Solution**:
1. Install MongoDB: `brew install mongodb-community` (macOS)
2. Or skip integration tests: `pytest -m "not mongo"`

### Tests Hang or Timeout

Some integration tests can be slow.

**Solution**:
- Increase timeout: `pytest --timeout=60`
- Or skip integration tests: `pytest tests/unit tests/smoke`

### Coverage Report Missing Lines

Coverage might not track all execution paths.

**Solution**:
- Check `.coveragerc` for excluded patterns
- Ensure tests actually exercise the code paths
- Use `--cov-report=html` to visualize coverage gaps

### Pre-commit Hooks Failing

Hooks might fail on first run due to missing dependencies.

**Solution**:
```bash
pre-commit clean
pre-commit install --install-hooks
pre-commit run --all-files
```

### Port Conflicts in Integration Tests

Multiple test runs might conflict on MongoDB ports.

**Solution**:
- Tests use unique ports per worker (pytest-xdist)
- If conflicts persist, reduce parallelism: `pytest -n 2`

## Coverage Goals

- **Target**: 100% line coverage for `wks/api`
- **Current**: 49.8% overall (actively improving)
- **Priority**: Core business logic in API layer
- **Excluded**: Auto-generated code, external interfaces

Track progress in README.md badges and CI dashboard.

## Additional Resources

- [CI Docker Image Documentation](ci-runner.md)
- [CONTRIBUTING.md](../../CONTRIBUTING.md) - Full development guide
- [pytest documentation](https://docs.pytest.org/)
- [mutmut documentation](https://mutmut.readthedocs.io/)
