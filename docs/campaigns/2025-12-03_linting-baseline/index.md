# Linting Baseline Campaign

**Date:** 2025-12-03
**Status:** 🟡 IN PROGRESS
**Branch:** `2025-12-03_linting-baseline`
**PR:** [#8](https://github.com/wawiesel/wks/pull/8)

---

## Executive Summary

This campaign aims to enable all warnings and linting checks that are currently disabled, fix all issues, and establish a super clean baseline for the codebase. This will improve code quality, catch bugs early, and ensure consistent code style across the project.

### Goals

1. ✅ Enable all ruff linting rules (currently only E, F, I, B are enabled)
2. ✅ Enable strict mypy checking (currently `strict=false`, `ignore_missing_imports=true`, `check_untyped_defs=false`)
3. ✅ Fix all formatting issues
4. ✅ Fix all linting errors
5. ✅ Fix all type checking errors
6. ✅ Ensure all tests still pass
7. ✅ Create a clean baseline for future development

---

## Current State Analysis

### Ruff Configuration

**Current:** Only 4 rule categories enabled
```toml
[tool.ruff.lint]
select = ["E", "F", "I", "B"]
```

**Issues Found:**
- 8 files need reformatting
- Import sorting issues (I001)
- Line length violations (E501)
- F-string without placeholders (F541)

### Mypy Configuration

**Current:** Very permissive settings
```toml
[tool.mypy]
strict = false
ignore_missing_imports = true
check_untyped_defs = false
```

**Issues Found:**
- ~40+ type errors currently ignored
- Missing type annotations
- Incompatible types
- Missing return statements
- Incorrect type usage

### Test Status

- ✅ All 694 tests passing
- ✅ Zero warnings after pytest.ini fix

---

## Changes Planned

### 1. Enable All Ruff Rules

Enable comprehensive ruff linting by selecting all rule categories:
- **E**: pycodestyle errors
- **W**: pycodestyle warnings
- **F**: pyflakes
- **I**: isort (import sorting)
- **N**: pep8-naming
- **UP**: pyupgrade
- **B**: flake8-bugbear
- **C4**: flake8-comprehensions
- **SIM**: flake8-simplify
- **ARG**: flake8-unused-arguments
- **PTH**: flake8-use-pathlib
- **ERA**: eradicate (commented-out code)
- **PD**: pandas-vet
- **PGH**: pygrep-hooks
- **PL**: Pylint
- **TRY**: tryceratops
- **NPY**: NumPy-specific rules
- **RUF**: Ruff-specific rules

### 2. Enable Strict Mypy

Change mypy configuration to:
```toml
[tool.mypy]
strict = true
ignore_missing_imports = false
check_untyped_defs = true
warn_unused_ignores = true
warn_redundant_casts = true
warn_unused_configs = true
warn_return_any = true
```

### 3. Fix All Issues

Systematically fix:
- Formatting issues (auto-fixable)
- Linting errors (many auto-fixable)
- Type errors (require code changes)

---

## Agent Delegation

This campaign is organized into three agent tasks:

### Agent 1: Fix Formatting and Basic Linting
**Goal:** Fix all auto-fixable formatting and basic linting issues
**Branch:** `2025-12-03_linting-baseline/agent1-formatting`
**Status:** 🟡 PENDING ASSIGNMENT
**Details:** See `agent1/GOAL.md`

Tasks:
- Fix formatting issues (ruff format)
- Fix unused variables (F841)
- Fix unused loop variables (B007)
- Fix ambiguous variable names (E741)
- Fix unused imports (F401)
- Fix line length violations (E501)
- Fix exception handling (B904)

### Agent 2: Enable Additional Ruff Rules
**Goal:** Gradually enable additional ruff linting rule categories and fix issues
**Branch:** `2025-12-03_linting-baseline/agent2-additional-rules`
**Status:** 🟡 PENDING ASSIGNMENT
**Details:** See `agent2/GOAL.md`

Tasks:
- Enable safe rule categories (W, N, UP, C4, SIM)
- Fix issues from new rules
- Enable more rules (ARG, PTH, RUF)
- Fix additional issues

### Agent 3: Enable Strict Mypy and Fix Type Errors
**Goal:** Enable strict mypy type checking and fix all type errors
**Branch:** `2025-12-03_linting-baseline/agent3-strict-mypy`
**Status:** 🟡 PENDING ASSIGNMENT
**Details:** See `agent3/GOAL.md`

Tasks:
- Enable `check_untyped_defs = true` and fix missing annotations
- Enable `ignore_missing_imports = false` and fix import issues
- Enable `strict = true` and fix all strict mode violations

---

## Progress Tracking

### Completed
- [x] Created campaign branch
- [x] Created campaign documentation
- [x] Analyzed current state

### Agent Status
- [ ] Agent 1: Formatting and basic linting (PENDING)
- [ ] Agent 2: Additional ruff rules (PENDING)
- [ ] Agent 3: Strict mypy (PENDING)

### Pending
- [ ] All agent PRs merged
- [ ] Final integration verification
- [ ] All tests pass
- [x] Campaign PR created

---

## Files Modified

*To be updated as work progresses*

---

## Lessons Learned

*To be updated as work progresses*

---

## Conclusion

*To be updated upon completion*
