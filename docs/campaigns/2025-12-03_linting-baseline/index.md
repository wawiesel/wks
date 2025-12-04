# Linting Baseline Campaign

**Date:** 2025-12-03
**Status:** 🟡 IN PROGRESS
**Branch:** `2025-12-03_linting-baseline`

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

## Implementation Plan

### Phase 1: Enable Ruff Rules (Incremental)

1. Start with additional safe rule categories:
   - `W` (warnings)
   - `N` (naming)
   - `UP` (upgrades)
   - `C4` (comprehensions)
   - `SIM` (simplify)

2. Fix issues from these rules

3. Gradually enable more rules:
   - `ARG` (unused arguments)
   - `PTH` (pathlib)
   - `ERA` (eradicate)
   - `RUF` (ruff-specific)

4. Enable remaining rules and fix issues

### Phase 2: Enable Strict Mypy

1. First enable `check_untyped_defs = true`
2. Fix missing type annotations
3. Enable `ignore_missing_imports = false`
4. Fix import-related type issues
5. Enable `strict = true`
6. Fix remaining strict mode issues

### Phase 3: Verification

1. Run full test suite
2. Verify all quality checks pass
3. Ensure no regressions

---

## Progress Tracking

### Completed
- [x] Created campaign branch
- [x] Created campaign documentation
- [x] Analyzed current state

### In Progress
- [ ] Enable additional ruff rules
- [ ] Fix formatting issues
- [ ] Fix linting errors

### Pending
- [ ] Enable strict mypy
- [ ] Fix type errors
- [ ] Verify all tests pass
- [ ] Create PR

---

## Files Modified

*To be updated as work progresses*

---

## Lessons Learned

*To be updated as work progresses*

---

## Conclusion

*To be updated upon completion*
