# Contributing to WKS

Follow `.cursor/rules/*`.

## Development Setup

For details on the CI Docker environment and running tests in containers, see **[docker/README.md](docker/README.md)**.

1. **Virtual Environment**: Always use a virtual environment.
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -e .
   ```

2. **Dependencies**: Install whatever you need in `.venv`.

3. **Merge Driver for Auto-Generated Files**: Configure the `ours` merge driver to avoid conflicts in CI-regenerated files:
   ```bash
   git config merge.ours.driver true
   ```
   This allows `qa/metrics/*.json` (which CI regenerates after every merge) to auto-resolve conflicts by keeping the current version—CI will regenerate the correct values.

## Git Commit Standards

We follow the **Conventional Commits** specification for clear and machine-readable commit history.

**Format**:
```text
<type>(<scope>): <subject>

<body>

<footer>
```

**Types**:
- `feat`: A new feature
- `fix`: A bug fix
- `docs`: Documentation only changes
- `style`: Changes that do not affect the meaning of the code (white-space, formatting, etc.)
- `refactor`: A code change that neither fixes a bug nor adds a feature
- `perf`: A code change that improves performance
- `test`: Adding missing tests or correcting existing tests
- `chore`: Changes to the build process or auxiliary tools and libraries

**Examples**:
- `feat(auth): implement jwt token validation`
- `fix(cli): resolve crash on missing config file`
- `docs: update contributing guidelines`

## Quality Checks & Hooks

To ensure code quality and consistency, we use a combination of local Git hooks and GitHub Actions.

### Local Pre-commit Hooks

We use `pre-commit` to manage Git hooks, which run automatically before you commit or push your changes. These hooks help catch common issues early in the development cycle.

**Setup**:
1. Install `pre-commit` (it's listed in `setup.py` and installed with `pip install -e .`).
2. Activate the hooks in your local Git repository:
   ```bash
   pre-commit install --hook-type pre-commit --hook-type pre-push
   ```
   This command installs scripts into your `.git/hooks` directory that will run the configured checks.

**Checks Performed**:
*   **`pre-commit` hooks**:
    *   `trailing-whitespace`: Removes extraneous whitespace at the end of lines.
    *   `end-of-file-fixer`: Ensures files end with a single newline.
    *   `check-yaml`: Checks YAML file syntax.
    *   `check-added-large-files`: Prevents committing very large files.
    *   `check-format.py`: Runs `ruff format --check` and `ruff check` (linting).
    *   `check-types.py`: Runs `mypy` for static type checking.
*   **`pre-push` hooks**:
    *   `pytest`: Runs the full test suite.
    *   `check-complexity.py`: Runs `lizard` for code complexity analysis.

To manually run all checks: `./scripts/check_quality.py [--fix]`
To manually run a specific check: `./scripts/check_format.py [--fix]`

### Continuous Integration (CI) Checks

Our GitHub Actions workflow (`.github/workflows/quality.yml`) enforces these same quality checks on every pull request. This ensures that all code merged into `main` adheres to our standards.

**Note on CI**: All tests in CI run inside our `ci-runner` Docker container. The container is the source of truth for dependencies. See [docker/README.md](docker/README.md) for details.

## Test Suites

We have three levels of tests, each runnable independently via scripts:

*   **Smoke Tests**: Quick, high-level tests to ensure basic functionality.
    ```bash
    ./scripts/test_smoke.py
    ```
*   **Unit Tests**: Isolated tests for individual functions and components.
    ```bash
    ./scripts/test_unit.py
    ```
*   **Integration Tests**: Tests that verify interactions between different components and external systems.
    ```bash
    ./scripts/test_integration.py
    ```

For comprehensive testing documentation, including writing tests and troubleshooting, see the [Writing Tests](#writing-tests) and [Troubleshooting Tests](#troubleshooting-tests) sections below. For Docker infrastructure, see [docker/README.md](docker/README.md).

## Mutation Testing (API)

We use `mutmut` for mutation testing of the Python API layer (`wks/api`).

```bash
./scripts/test_mutation_api.py
```

Notes:
- This is intentionally **not** part of the default pre-push hook (it can be slow).
- Configuration lives in `setup.cfg` under `[mutmut]` (notably `paths_to_mutate` and `tests_dir`).
- The script prints a summary by default. Use `--verbose` to print the full mutant listing.
- You can enforce a target mutation score via `setup.cfg` `[wks.mutation] min_kill_rate = 0.90` (or override with `--min-kill-rate 0.90`).

## README Statistics

The code quality metrics in `README.md` (mutation score, test counts, etc.) are automatically kept in sync with the codebase
   - **Stats**: `qa/metrics/*.json` (aggregated statistics)
   - **Reports**: `mutants/` (detailed mutation results)

   Steps:
   1. **Generate**: Tools write raw data to `qa/metrics/`.
   2. **Aggregate**: `scripts/update_readme_stats.py` reads `qa/metrics/` and updates `README.md`.
 and stored in `qa/metrics/*.json`.

**Automatic Updates**:
- **Local**: The statistics are updated automatically via a `pre-commit` hook when `README.md` is modified.
- **CI**: On pushes to `main`/`master`, GitHub Actions automatically runs mutation tests and updates the README statistics, then commits the changes back.
- **PRs**: Pull requests will fail CI if the README statistics are out of date, ensuring stats stay current.

**Manual Update**:
If you need to manually update the statistics (e.g., after running mutation tests):
```bash
./scripts/update_readme_stats.py
```

The script collects:
- Mutation score (from `mutmut results`)
- Test count (from `pytest`)
- Test file count
- Code statistics broken down by section (`wks/api`, `wks/cli`, `wks/mcp`, `wks/utils`):
  - File count
  - Lines of code (LOC)
  - Characters
  - Python tokens (using `tokenize` module)

Metrics outputs are stored under `qa/metrics/` for CI and tooling.

**CI Workflow**:
The `.github/workflows/update-stats.yml` workflow:
1. Runs tests and mutation tests
2. Updates README statistics
3. On `main`/`master` pushes: Auto-commits updated stats (with `[skip ci]` to avoid loops)
4. On PRs: Fails if stats are outdated, requiring the PR author to update them

**Visualization**:
Generate a visual representation of codebase statistics:
### Generating Codebase Visualization

To generate a visual representation of codebase statistics:

```bash
pip install matplotlib  # Required for visualization
./scripts/generate_codebase_visualization.py
   - `scripts/generate_token_stats.py` -> `qa/metrics/tokens.json`
   - `scripts/test_mutation_api.py` -> `qa/metrics/mutations.json` (updates incrementally per domain)
```

This creates `docs/codebase_stats.png` with a multi-panel visualization showing:
- **Distribution by category** (pie chart): Shows the proportion of code, infrastructure, docs, and tests
- **All sections comparison** (horizontal bar chart): Breakdown of all sections with percentages
- **Totals by category** (stacked bar chart): Totals grouped by category

The visualization automatically reads statistics from the README.md tables. The generated PNG file is excluded from git (via `.gitignore`) to avoid committing large binary files.

## Coding Standards

### General Principles
- **DRY (Don't Repeat Yourself)**: Zero code duplication between CLI and MCP.
- **KISS (Keep It Simple, Stupid)**: Eliminate unnecessary features and complexity.
- **No Hedging**: Remove fallback logic. No silent defaults or implicit substitutions. Fail fast and visibly.
- **No Internal Backwards Compatibility Shims**: Do not add compatibility wrappers or legacy code paths inside this repository to support older call sites (e.g., "compat" helpers that quietly reshape configs or emulate old behavior). Instead, update all callers to the new interfaces and raise clear, actionable errors when inputs are invalid or incomplete.

### Code Metrics
- **Complexity**: Use `lizard` to measure metrics.
  - **CCN (Cyclomatic Complexity Number)**: Must be ≤ 10 per function.
  - **NLOC (Non-Comment Lines of Code)**: Must be ≤ 100 per function.
- **File Size**: If a file exceeds 900 lines, break it up (includes tests).

### Type Safety & Data Structures
- **Strong Typing**: Favor strong typing over dynamic typing.
- **Dataclasses over Dicts**: Use `dataclasses` for all structured data (configuration, DTOs, API responses). Pass dataclasses between layers, not dictionaries. Use `to_dict()` only at serialization boundaries (JSON output, MCP responses).
- **Validation**: Validate strictly on load (`__post_init__`). Fail immediately if data is invalid.

### Error Handling
- **Structured Aggregation**: Replace ad-hoc error handling with structured aggregation. Collect all errors and raise them together.
- **Deterministic Behavior**: Fail fast and visibly. Avoid optional or hidden recovery logic.
- **Logging**:
  - Use a logger for all info/debug/warning/error conditions.
  - **MCP**: Send warning/errors in the JSON packet.
  - **CLI**: Emit warnings/errors to STDERR. Info/debug goes to logs only.

## Architecture & Design Principles

### Layered Architecture

WKS follows a three-layer architecture with clear separation of concerns:

1. **Python API (Core Business Logic)**
   - Controllers, business logic, data structures
   - Beautiful, well-tested code with 100% test coverage
   - No UI concerns, no protocol-specific code
   - Located in `wks/` package modules (e.g., `wks.monitor.controller`, `wks.transform.controller`)
   - Pure Python functions/classes that can be imported and used directly

2. **MCP Server Layer (Thin Protocol Wrapper)**
   - Thin layer on top of the Python API
   - Translates MCP protocol requests to API calls
   - Returns structured results via `MCPResult` (with data, messages, errors)
   - MCP is the **source of truth** for all errors, warnings, and messages
   - Located in `wks/mcp.py` and `wks/mcp/`
   - All MCP tools call the Python API, never duplicate business logic

3. **CLI Layer (Thin User Interface Wrapper)**
   - Thin layer that **only** calls MCP tools
   - Formats MCP results for human-readable output
   - Handles stdin/stdout/stderr according to CLI guidelines
   - Located in `wks/cli/`
   - **All** CLI commands call MCP tools via `call_tool()` - zero business logic in CLI
   - No exceptions: every CLI command is just argument parsing + MCP call + output formatting

**Design Decisions:**
- **MCP as Source of Truth**: CLI calls MCP tools rather than duplicating logic. This ensures consistency and makes MCP the authoritative interface.
- **No Business Logic in CLI**: CLI is strictly argument parsing, MCP tool calls, and output formatting. All business logic is in the Python API, called by MCP.
- **Structured Results**: MCP tools return `MCPResult` objects with structured data, messages, errors, and warnings. CLI consumes and formats these.
- **Zero Duplication**: Business logic exists only in the Python API. MCP and CLI are thin wrappers.
- **Testability**: The Python API can be tested independently of MCP or CLI protocols.
- **Flow**: `CLI → MCP → API` - CLI never calls API directly, MCP never contains business logic

### Error Handling & Logging (Architecture)

**Single Source of Truth**: All errors, warnings, and messages originate in MCP tools (which call the Python API).
- MCP tools return structured `MCPResult` objects with:
  - `success`: bool
  - `data`: dict (actual result data)
  - `messages`: list of structured messages (error, warning, info, status)
  - `log`: optional list of log entries for debugging
- CLI consumes `MCPResult` and formats messages appropriately:
  - Errors/Warnings/Info → STDERR
  - Status messages → STDERR
  - Result data → STDOUT (if success)
- MCP protocol sends warnings/errors in JSON-RPC response packets

### Design Patterns
- **Strategy Pattern**: Use for display modes and engine implementations.
- **Controller Pattern**: Centralize business logic in controllers shared by CLI and MCP.

## Command Execution Pattern (CLI & MCP)

Every command (CLI or MCP) must follow this 4-step behavior:
1. **Announce**: Immediately say what you are doing (CLI: STDERR, MCP: status message).
2. **Progress**: Start a progress indicator with time estimate (CLI: progress bar on STDERR, MCP: progress notifications).
3. **Result**: Say what you did and report problems (CLI: STDERR, MCP: result notification messages).
4. **Output**: Display the final output (CLI: STDOUT, MCP: result notification data).
   - Use colorized output (red for failures).
   - Show OK/FAIL status before the last error.
   - If failed, output should be empty (CLI: STDOUT empty, MCP: data empty).

### Implementing the 4-Step Pattern with Typer

For Typer-based commands, use the `Display` object to follow the pattern. The same pattern works for both CLI and MCP:

```python
from typer import Typer
from ..display.context import get_display
from ..mcp.result import MCPResult, Message, MessageType

@monitor_app.command(name="status")
def monitor_status(display=None):
    """Get monitor status."""
    # Step 1: Announce (STDERR)
    if display is None:
        display = get_display("cli")
    display.status("Checking monitor status...")

    # Step 2: Progress (STDERR) - using context manager
    try:
        with display.progress(total=1, description="Querying monitor..."):
            # Business logic here
            from ..monitor.controller import MonitorController
            from ..config import WKSConfig

            config = WKSConfig.load()
            status = MonitorController.get_status(config.monitor)

        # Step 3: Result (STDERR)
        display.success("Monitor status retrieved successfully")

        # Step 4: Output (STDOUT) - return data for decorator to handle
        return MCPResult(success=True, data=status.model_dump(), messages=[])
    except Exception as e:
        display.error(f"Failed to get monitor status: {e}")
        return MCPResult(
            success=False,
            data={},
            messages=[Message(type=MessageType.ERROR, text=str(e))]
        )
```

**Progress Bar Patterns:**
- **Simple operation**: Use `with display.progress(total=1, description="..."):` for instant operations
- **Iterative operation**: Use `display.progress_start()`, `display.progress_update()`, `display.progress_finish()` for multi-step operations
- **Context manager**: The `display.progress()` context manager automatically handles start/finish

**Display Object:**
- `display.status()`, `display.success()`, `display.error()`, `display.warning()` → STDERR
- `display.json_output()` → STDOUT
- Progress bars automatically go to STDERR

## Testing

- **Validation**: Ensure remaining tests pass after refactoring.

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

## Troubleshooting Tests

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

## Docker Testing Infrastructure

For details on the Docker CI image management, versioning, and running tests in Docker, see [docker/README.md](docker/README.md).
