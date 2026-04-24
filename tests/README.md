# Test Suite for WKS

This directory contains the comprehensive test suite for the WKS project, ensuring the quality, correctness, and adherence to architectural principles. The tests are organized into `unit`, `smoke`, and `integration` categories, each serving a distinct purpose in the testing strategy.

## Traceability

Tests list requirement IDs in their docstrings under a `Requirements:` block. The traceability audit scans these docstrings and uses the test file path as the test identifier (no extra metadata files or HODOR-specific comments).

Example:

```
def test_cmd_status_success():
    """Status succeeds with default config and no issues.

    Requirements:
    - MON-003
    """
```

## Testing Strategy

The WKS project employs a layered testing strategy designed to provide thorough coverage at different levels of abstraction:

### Unit Tests (`tests/unit/`)

**Purpose**: Unit tests verify the correctness of the shared execution layers:
- the **service/core layer** (`wks/services/*`) for deep business-logic coverage
- the **command layer** (`wks/api/*/cmd*.py`) for per-command contract coverage

**Principles**:
-   **PUTT PUTT Rule**: Every public function or class within `wks/services/*` and `wks/api/*` must have **100% unit test coverage**. No exceptions.
-   **UMP Rule**: Private modules (`_*.py` files, functions, or classes) are not tested directly. Their coverage is achieved implicitly by exercising the public API functions that utilize them.
-   **Isolation**: Mocks are used to isolate the shared service/core and command layers from external dependencies where appropriate.
-   **Naming Convention**:
    - `test_wks_service_<domain>.py` for shared service/core logic
    - `test_wks_api_<domain>_<module>.py` for command wrappers

### Integration Tests (`tests/integration/`)

**Purpose**: Integration tests verify the functionality and interaction of **cross-module components** and **external systems**. This includes:
- **CLI Logic**: Testing `Typer` commands and argument resolution (`test_wks_cli_<domain>.py`).
- **MCP Layer**: Verifying tool registration and JSON-RPC handling.
- **REST Layer**: Verifying HTTP routing and status mapping over the shared services.
- **System Ops**: Testing service installation and OS interactions.

**Principles**:
-   **Wiring Focus**: Verify that layers connect correctly (CLI -> command, MCP -> command, REST -> service).
-   **Execution**: Use `TyperRunner` for CLI, or direct component instantiation.
-   **Real & Validated**: Use real configurations and validation logic.
-   **Naming**: `test_wks_cli_<domain>.py`, `test_mcp_<domain>.py`.

### Smoke Tests (`tests/smoke/`)

**Purpose**: Smoke tests verify that installed entry points are executable by a user. They provide an end-to-end "smoke check" of the deployed application.

**Principles**:
-   **Binary Execution**: Invoke installed entry points such as `wksc`, `wksm`, and `wksr` via subprocesses.
-   **User Perspective**: Test arguments, exit codes, and standard I/O as a user sees them.
-   **End-to-End**: No internal mocking if possible; rely on the actual installed environment (or simulated home dir).
-   **Naming Convention**: `test_wksc_<domain>.py`.

## Running Tests

-   To run all unit tests for the service/core and command layers: `pytest tests/unit/`
-   To run all integration tests for the transport layers: `pytest tests/integration/`
-   To run all smoke tests for installed entry points: `pytest tests/smoke/`
-   To run all tests: `pytest`
-   To check coverage for the API layer (unit tests): `pytest --cov=wks/api tests/unit/`
-   To check coverage for the MCP layer (integration tests): `pytest --cov=wks/mcp tests/integration/`
-   Full coverage report: `./scripts/run_coverage.sh`

---

**Note**: This testing strategy ensures that each layer is robustly tested according to its role in the application architecture, providing confidence in the overall system's correctness and reliability.
