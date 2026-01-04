# Test Suite for WKS

This directory contains the comprehensive test suite for the WKS project, ensuring the quality, correctness, and adherence to architectural principles. The tests are organized into `unit`, `smoke`, and `integration` categories, each serving a distinct purpose in the testing strategy.

## Testing Strategy

The WKS project employs a layered testing strategy designed to provide thorough coverage at different levels of abstraction:

### Unit Tests (`tests/unit/`)

**Purpose**: Unit tests are focused exclusively on verifying the correctness of the **API layer** (`wks/api/*`). They test individual API functions, classes, and private helpers in isolation. The primary goal is to ensure that the core business logic, data models, and domain-specific operations (e.g., monitor priority calculation, database interactions via API) function as expected according to their specifications.

**Principles**:
-   **PUTT PUTT Rule**: Every public function or class within `wks/api/*` must have **100% unit test coverage**. No exceptions.
-   **UMP Rule**: Private modules (`_*.py` files, functions, or classes) are not tested directly. Their coverage is achieved implicitly by exercising the public API functions that utilize them.
-   **Isolation**: Mocks are extensively used to isolate the API layer from external dependencies (e.g., file system, database connections, CLI/MCP layers). This ensures that API tests are fast, reliable, and pinpoint failures accurately.
-   **Naming Convention**: `test_wks_api_<domain>_<module>.py` (e.g., `test_wks_api_monitor_cmd_status.py`).

### Integration Tests (`tests/integration/`)

**Purpose**: Integration tests verify the functionality and interaction of **cross-module components** and **external systems**. This includes:
- **CLI Logic**: Testing `Typer` commands and argument resolution (`test_wks_cli_<domain>.py`).
- **MCP Layer**: Verifying tool registration and JSON-RPC handling.
- **System Ops**: Testing service installation and OS interactions.

**Principles**:
-   **Wiring Focus**: Verify that layers connect correctly (CLI -> API, MCP -> API).
-   **Execution**: Use `TyperRunner` for CLI, or direct component instantiation.
-   **Real & Validated**: Use real configurations and validation logic.
-   **Naming**: `test_wks_cli_<domain>.py`, `test_mcp_<domain>.py`.

### Smoke Tests (`tests/smoke/`)

**Purpose**: Smoke tests verify that the **`wksc` binary** is installed and executable by a user. They provide an end-to-end "smoke check" of the deployed application.

**Principles**:
-   **Binary Execution**: Invoke `wksc` via subprocesses. `wksc` must be in PATH or venv.
-   **User Perspective**: Test arguments, exit codes, and standard I/O as a user sees them.
-   **End-to-End**: No internal mocking if possible; rely on the actual installed environment (or simulated home dir).
-   **Naming Convention**: `test_wksc_<domain>.py`.

## Running Tests

-   To run all unit tests for the API layer: `pytest tests/unit/`
-   To run all integration tests for the MCP layer: `pytest tests/integration/`
-   To run all smoke tests for the CLI layer: `pytest tests/smoke/`
-   To run all tests: `pytest`
-   To check coverage for the API layer (unit tests): `pytest --cov=wks/api tests/unit/`
-   To check coverage for the MCP layer (integration tests): `pytest --cov=wks/mcp tests/integration/`
-   Full coverage report: `./scripts/run_coverage.sh`

---

**Note**: This testing strategy ensures that each layer is robustly tested according to its role in the application architecture, providing confidence in the overall system's correctness and reliability.
