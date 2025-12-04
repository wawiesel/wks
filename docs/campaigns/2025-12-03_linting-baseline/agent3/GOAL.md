# Agent 3 Goal: Enable Strict Mypy and Fix Type Errors

**Agent:** Agent 3
**Branch:** `2025-12-03_linting-baseline/agent3-strict-mypy`
**Status:** 🟡 PENDING ASSIGNMENT

---

## Objective

Enable strict mypy type checking and fix all type errors. This should be done incrementally to avoid breaking changes.

## Tasks

### Phase 1: Enable `check_untyped_defs`

Update `pyproject.toml`:
```toml
[tool.mypy]
python_version = "3.10"
strict = false
ignore_missing_imports = true
check_untyped_defs = true  # Enable this first
```

Fix all missing type annotations for function arguments and return types.

### Phase 2: Fix Missing Type Annotations

Add type annotations to all functions that need them. Focus on:
- Function parameters
- Return types
- Class attributes
- Module-level variables

### Phase 3: Enable `ignore_missing_imports = false`

Update `pyproject.toml`:
```toml
[tool.mypy]
ignore_missing_imports = false  # Enable this
```

Fix import-related type issues:
- Add type stubs for missing packages
- Use `# type: ignore` only when absolutely necessary
- Document why ignores are needed

### Phase 4: Enable Strict Mode

Update `pyproject.toml`:
```toml
[tool.mypy]
strict = true
warn_unused_ignores = true
warn_redundant_casts = true
warn_unused_configs = true
warn_return_any = true
```

Fix all strict mode violations:
- Incompatible types
- Missing return statements
- Incorrect type usage
- Any/None type issues

## Known Issues to Fix

Based on initial analysis, fix these categories:

### Missing Type Annotations
- `wks/monitor/config.py:35` - `errors` list
- `wks/transform/config.py:89, 102, 135, 148` - `errors` lists
- `wks/diff/config.py:46, 59, 72, 104, 187` - `errors` lists
- `wks/db_helpers.py:126` - `client` variable
- `wks/vault/status_controller.py:79` - `client` variable
- `wks/monitor/controller.py:142, 450, 513` - `client` variables
- `wks/vault/indexer.py:444` - `client` variable
- `wks/vault/controller.py:77` - `client` variable
- `wks/vault/controller.py:153` - `broken_by_status` dict

### Incompatible Types
- `wks/display/context.py:37` - Optional mode argument
- `wks/config.py:95` - TransformConfig arguments
- `wks/service_controller.py:224` - int() argument
- `wks/filesystem_monitor.py:121, 124, 126, 133, 138, 141, 142, 169, 176, 178, 180` - bytes/str type issues
- `wks/filesystem_monitor.py:211` - Observer type
- `wks/monitor/operations.py:19` - `any` vs `Any`
- `wks/mcp_server.py:387, 390, 396, 401, 479, 508, 533, 536, 538` - Various type issues

### Missing Return Statements
- `wks/transform/controller.py:60`

### Function Type Issues
- `wks/mcp_server.py:390, 396` - `callable` vs `Callable`

## Success Criteria

- [ ] `check_untyped_defs = true` enabled and all issues fixed
- [ ] `ignore_missing_imports = false` enabled and all issues fixed
- [ ] `strict = true` enabled and all issues fixed
- [ ] All files pass `mypy` with strict mode
- [ ] All tests still pass (694 tests)
- [ ] Type safety significantly improved

## Branch Strategy

1. Create branch from `2025-12-03_linting-baseline`
2. Enable mypy options incrementally (one phase at a time)
3. Fix issues for each phase before moving to next
4. Run tests after each phase
5. Create PR targeting `2025-12-03_linting-baseline`
6. Wait for Orchestrator review and merge

## Notes

- Use `typing` module for type hints (e.g., `List`, `Dict`, `Optional`, `Any`)
- For MongoDB client types, use `pymongo.MongoClient` or create type aliases
- For complex types, consider using `TypedDict` or `Protocol`
- Use `# type: ignore` sparingly and document why
- Prefer explicit types over `Any` when possible
- For third-party libraries without stubs, consider creating local stubs or using `types-*` packages
