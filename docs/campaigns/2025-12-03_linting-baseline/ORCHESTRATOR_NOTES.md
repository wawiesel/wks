# Orchestrator Monitoring Notes

**Campaign:** Linting Baseline
**Date Started:** 2025-12-03
**Status:** 🟡 Agents Active

---

## Agent Status

### Agent 1: Formatting and Basic Linting
**Branch:** `agent1-formatting`
**Status:** 🟡 ACTIVE
**PR:** *Not yet created*

**Monitoring Checklist:**
- [ ] PR created targeting `2025-12-03_linting-baseline`
- [ ] All formatting issues fixed (`ruff format --check` passes)
- [ ] All basic linting errors fixed (F841, B007, E741, F401, E501, B904)
- [ ] All 694 tests still pass
- [ ] No functionality changes (only formatting/linting)

**Common Issues to Watch For:**
- Unused loop variable `i` in `tests/integration/test_vault_controller_full.py:174` - needs to be `_` or actually used
- Line length violations - ensure breaks are at logical points
- Exception handling - use `raise ... from err` or `raise ... from None` appropriately

**Helpful Hints:**
- Use `ruff format --fix` first, then `ruff check --fix` for auto-fixable issues
- For unused variables, check if they're actually needed or can be removed
- For line length, break after commas or before operators for readability

---

### Agent 2: Additional Ruff Rules
**Branch:** `agent2-additional-rules`
**Status:** 🟡 ACTIVE
**PR:** *Not yet created*

**Monitoring Checklist:**
- [ ] PR created targeting `2025-12-03_linting-baseline`
- [ ] Phase 1 rules enabled (W, N, UP, C4, SIM) and all issues fixed
- [ ] Phase 3 rules enabled (ARG, PTH, RUF) and all issues fixed
- [ ] All tests still pass
- [ ] Code quality improved

**Common Issues to Watch For:**
- Naming violations (N) - ensure Python naming conventions followed
- Unused arguments (ARG) - may be needed for interface compatibility
- Pathlib usage (PTH) - ensure conversions are correct
- Auto-fixes that change behavior - review carefully

**Helpful Hints:**
- Enable rules incrementally - don't enable all at once
- Fix Phase 1 completely before moving to Phase 3
- Review auto-fixes to ensure they don't break functionality
- For unused arguments, consider if they're part of an interface that can't be changed

---

### Agent 3: Strict Mypy
**Branch:** `agent3-strict-mypy`
**Status:** 🟡 ACTIVE
**PR:** *Not yet created*

**Monitoring Checklist:**
- [ ] PR created targeting `2025-12-03_linting-baseline`
- [ ] Phase 1: `check_untyped_defs = true` enabled and all annotations added
- [ ] Phase 3: `ignore_missing_imports = false` enabled and import issues fixed
- [ ] Phase 4: `strict = true` enabled and all strict violations fixed
- [ ] All tests still pass
- [ ] Type safety significantly improved

**Common Issues to Watch For:**
- Missing type annotations for `errors` lists - should be `list[str]`
- MongoDB client types - use `pymongo.MongoClient` or type aliases
- Optional types - use `Optional[...]` or `... | None` (Python 3.10+)
- Bytes vs str issues in filesystem_monitor - ensure proper type conversions
- Missing return statements - add explicit returns or `-> None`

**Helpful Hints:**
- Work incrementally - each phase must be complete before moving to next
- Use `typing` module imports (List, Dict, Optional, Any)
- For complex types, consider TypedDict or Protocol
- Use `# type: ignore` sparingly and always document why
- For third-party libraries, check if `types-*` packages exist

---

## Review Process

When an agent creates a PR:

1. **Initial Review:**
   - Check that PR targets `2025-12-03_linting-baseline`
   - Verify all tests pass
   - Check that quality checks pass (`check_format.py`, `check_types.py`)
   - Review changes for correctness

2. **Provide Feedback:**
   - Point out any issues found
   - Suggest improvements
   - Approve if ready

3. **Merge:**
   - Merge PR into campaign branch
   - Update campaign documentation
   - Notify agent

---

## Quick Check Commands

```bash
# Check for new PRs
gh pr list --base 2025-12-03_linting-baseline

# Check agent branch status
git fetch origin
git log origin/agent1-formatting --oneline -5
git log origin/agent2-additional-rules --oneline -5
git log origin/agent3-strict-mypy --oneline -5

# Review specific PR
gh pr view <number> --comments
gh pr diff <number>
```

---

## Notes

- Agents should work independently on their branches
- Agents should sync with campaign branch regularly: `git pull origin 2025-12-03_linting-baseline`
- All PRs must target the campaign branch, not main
- All tests must pass before merging
- Quality checks must pass before merging
