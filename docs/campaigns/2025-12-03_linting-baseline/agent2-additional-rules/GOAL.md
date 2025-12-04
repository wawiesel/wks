# Agent 2 Goal: Enable Additional Ruff Rules

**Agent:** Agent 2
**Branch:** `agent2-additional-rules`
**Status:** 🟡 PENDING ASSIGNMENT

---

## Objective

Gradually enable additional ruff linting rule categories and fix all resulting issues. This should be done incrementally to ensure we catch issues without overwhelming the codebase.

## Tasks

### Phase 1: Enable Safe Rule Categories

Enable these rule categories in `pyproject.toml`:
```toml
[tool.ruff.lint]
select = ["E", "F", "I", "B", "W", "N", "UP", "C4", "SIM"]
```

#### Rule Categories:
- **W**: pycodestyle warnings (style issues)
- **N**: pep8-naming (naming conventions)
- **UP**: pyupgrade (modernize Python syntax)
- **C4**: flake8-comprehensions (better comprehensions)
- **SIM**: flake8-simplify (code simplification)

### Phase 2: Fix Issues from Phase 1

Fix all issues reported by the new rules. Many will be auto-fixable with `ruff check --fix`.

### Phase 3: Enable More Rules

After Phase 1 is clean, enable additional categories:
```toml
[tool.ruff.lint]
select = ["E", "F", "I", "B", "W", "N", "UP", "C4", "SIM", "ARG", "PTH", "RUF"]
```

#### Additional Categories:
- **ARG**: flake8-unused-arguments (unused function arguments)
- **PTH**: flake8-use-pathlib (prefer pathlib over os.path)
- **RUF**: Ruff-specific rules (Ruff's own linting rules)

### Phase 4: Fix Issues from Phase 3

Fix all issues from the additional rules.

### Phase 5: Enable Remaining Rules (Optional)

If time permits and Director approves, enable remaining categories:
- **ERA**: eradicate (commented-out code)
- **PGH**: pygrep-hooks (grep-based checks)
- **PL**: Pylint (additional style checks)
- **TRY**: tryceratops (exception handling best practices)

## Success Criteria

- [ ] Phase 1 rules enabled and all issues fixed
- [ ] Phase 3 rules enabled and all issues fixed
- [ ] All files pass `ruff check` with enabled rules
- [ ] All tests still pass (694 tests)
- [ ] Code quality improved (fewer potential bugs, better style)

## Branch Strategy

1. Create branch from `2025-12-03_linting-baseline`
2. Enable rules incrementally (one phase at a time)
3. Fix issues for each phase before moving to next
4. Run tests after each phase
5. Create PR targeting `2025-12-03_linting-baseline`
6. Wait for Orchestrator review and merge

## Notes

- Use `ruff check --fix` to auto-fix issues where possible
- Review auto-fixes to ensure they don't change behavior
- For naming issues (N), follow Python naming conventions:
  - Functions/variables: `snake_case`
  - Classes: `PascalCase`
  - Constants: `UPPER_SNAKE_CASE`
- For UP (pyupgrade), these are generally safe modernizations
- For ARG (unused arguments), consider if arguments are needed for interface compatibility
