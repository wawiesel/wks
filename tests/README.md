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

**Purpose**: Integration tests are designed to verify the functionality and interaction of components within the **MCP layer** (`wks/mcp/*`). They ensure that MCP tools are correctly registered, handle input/output, and properly interact with the underlying API layer.

**Principles**:
-   **Real Behavior**: Avoid using mocks where possible. Integration tests should interact with real components (e.g., `MCPServer`, underlying API functions).
-   **Local Configuration**: Utilize temporary directories and real (or mockable, e.g., `mongomock`) local configurations to simulate realistic environments without affecting the system.
-   **Coverage Focus**: Aim for 100% coverage of the `wks/mcp/*` components by exercising them in real-world scenarios.
-   **No CLI Paths**: Keep CLI coverage out of integration; CLI entrypoints are validated by the smoke suite.
-   **Naming Convention**: `test_mcp_*.py` (e.g., `test_mcp_server.py`).

### Smoke Tests (`tests/smoke/`)

**Purpose**: Smoke tests are quick, high-level checks to ensure the **CLI layer** (`wks/cli/*`) is fundamentally working. They are designed to provide rapid feedback on the health of the CLI application, ensuring that key commands execute without crashing and produce expected outputs.

**Principles**:
-   **Real CLI Execution**: Invoke the `wksc` command directly via subprocesses, just as a user would.
-   **Speed**: Tests must be fast to execute, providing an immediate "all clear" or "something is broken" signal.
-   **Basic Functionality**: Focus on whether essential commands work and provide output, rather than exhaustive coverage of every code path.
-   **No Mocks**: Completely avoid mocks. Smoke tests should simulate the end-user experience as closely as possible, using temporary local configurations.
-   **Naming Convention**: `test_cli_*.py` (e.g., `test_cli_smoke.py`).

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
