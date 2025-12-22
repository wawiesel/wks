---
alwaysApply: true
---

# Directives for AI

## First Priority: Rules Before Action

Before implementing any code change, you MUST:

1. **Identify which `.cursor/rules/*` apply** to the change you're about to make.
2. **Verify your proposed solution satisfies those rules** — especially DRY, NoHedging, and architectural boundaries.
3. **If in doubt, check the existing patterns** in the codebase (wrappers, handlers, facades) before adding new logic.

This is not optional. This is the first thing you think about every time.

---

*   **Authentication**: Under no circumstances authenticate yourself as a human user. You will always use a bot account. If you are unsure which bot account to use, you need to ask.

Follow all `.cursor/rules/*`.

If you are an AI agent doing coding, here is some help for you. For **all contributors (human and AI)**, please refer to the primary `CONTRIBUTING.md` for a comprehensive guide on development setup, coding standards, commit messages, and quality processes. This document provides supplementary directives specifically for AI agents.

*   Use the virtual environment. If it doesn't exist create one in `.venv`. You can install whatever you want there.
    - If `pytest` (or other tools) are missing, stop and bootstrap immediately: `python3 -m venv .venv && .venv/bin/pip install -e .`
    - Run tests and scripts via the venv (`.venv/bin/pytest`, `./scripts/test_*`) so they never silently skip.
*   **Adhere to Git Commit Standards**: All commit messages (and Pull Request titles for 'squash and merge' workflows) must follow the Conventional Commits specification documented in `CONTRIBUTING.md`.
*   **Respect Quality Checks**:
    *   Before pushing, ensure all `pre-commit` and `pre-push` hooks pass. These are defined in `.pre-commit-config.yaml` and leverage scripts in the `scripts/` directory.
    *   Specifically, this includes:
        *   Formatting and Linting (`ruff`) via `scripts/check_format.py`.
        *   Static Type Checking (`mypy`) via `scripts/check_types.py`.
        *   Code Complexity Analysis (`lizard`) via `scripts/check_complexity.py`.
    *   Refer to `CONTRIBUTING.md` for how to install and use `pre-commit` locally.
    *   Continuous Integration (CI) checks on GitHub will also enforce these standards.
*   **Run Tests**:
    *   Always run the full test suite (`pytest`) before pushing. This is part of the `pre-push` hook.
    *   For specific test levels, use the independent test scripts:
        *   Smoke tests: `./scripts/test_smoke.py`
        *   Unit tests: `./scripts/test_unit.py`
        *   Integration tests: `./scripts/test_integration.py`
    *   For detailed testing procedures and troubleshooting, see [CONTRIBUTING.md](CONTRIBUTING.md#testing). For Docker CI info, see [docker/README.md](docker/README.md).
*   Eliminate unnecessary features and legacy code wherever possible—remove complexity, redundant state, backward compatibility, and unused paths.
*   Support **only CLI and MCP** interfaces; drop all other modes.
*   Consolidate configuration to minimal, essential parameters.
*   Centralize configuration access through **dataclasses** instead of dictionaries. Validate strictly on load (`__post_init__`) and fail immediately if expected data or formats are missing.
*   Remove fallback logic (“hedging”); no silent defaults or implicit substitutions.
*   Represent databases as `<collection>.<database>` and fail hard if not found.
*   Include clear validation and precise error reporting with explicit paths, found values, and expected values.
*   For user-facing commands such as `wksc service status`, support a **live-updating display** with the `--live` flag.
*   Use colorized output—red for false or failed states—and show OK/FAIL status before the last error.
*   Keep tables simple and grouped by logical sections when appropriate.
*   Apply **DRY**, **KISS**, and no-hedge principles throughout.
*   Use `lizard` to measure code metrics (**CCN** and **NLOC**) and split any function with **CCN > 10** or **NLOC > 100**.
*   Apply clear design patterns, especially the **Strategy Pattern** for display modes.
*   Remove or disable obsolete tests tied to deprecated functionality and ensure remaining tests pass after refactoring.
*   Replace ad-hoc error handling with structured aggregation—collect all errors, then raise them together for full diagnostics.
*   Fail fast, fail visibly, and keep system behavior deterministic.
*   Avoid optional or hidden recovery logic.
*   Centralize validation and configuration handling at the lowest level.
*   Favor strong typing, dataclasses, and explicit structure over dynamic or dictionary-based access.
*   If a single file is more than 900 lines, break it up. This includes tests.
*   Use a logger for all informational/debug and warning/error conditions. Output the informational debug content to logs only. In MCP mode, send warning/errors in the returned JSON packet. In CLI mode, emit warnings/errors to STDERR. Information/debug should not be emitted to CLI (only logs). CLI STDOUT should always just be the expected content. If the error is so bad no content can be rendered, then STDOUT should be empty.
*   Every CLI command needs to do 4 things: 1) immediately say what you are doing on STDERR, 2) on STDERR start a progress bar for doing it, 3) on STDERR say what you did and if there were problems, 4) display the output on STDOUT
