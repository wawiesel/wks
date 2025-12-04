# Agent 4 Goal: Fix Complexity Violations

**Agent:** Agent 4
**Branch:** `agent4-complexity`
**Status:** 🟡 PENDING ASSIGNMENT

---

## Objective

Fix all code complexity violations to meet the project's complexity standards (CCN <= 10, NLOC <= 100). This ensures code maintainability and readability.

## Complexity Standards

From `CONTRIBUTING.md`:
- **CCN (Cyclomatic Complexity Number)**: Must be <= 10
- **NLOC (Non-Comment Lines of Code)**: Must be <= 100

The project uses `lizard` to measure complexity. Run:
```bash
lizard -l python -C 10 -L 100 wks
```

## Current Violations

There are **28 functions** that violate complexity standards. Priority order (by CCN, then NLOC):

### High Priority (CCN >= 14)
1. `get_changes@77-147@wks/vault/git_watcher.py` - CCN: 14, NLOC: 40
2. `get_changed_since_commit@149-210@wks/vault/git_watcher.py` - CCN: 14, NLOC: 39
3. `_maybe_flush_pending_deletes@650-699@wks/daemon.py` - CCN: 14, NLOC: 39
4. `_maybe_prune_monitor_db@599-648@wks/daemon.py` - CCN: 14, NLOC: 38
5. `_maybe_flush_pending_mods@701-737@wks/daemon.py` - CCN: 14, NLOC: 33

### Medium Priority (CCN 11-13)
6. `__init__@35-53@wks/monitor_rules.py` - CCN: 13, NLOC: 19
7. `_read_message@311-345@wks/mcp_server.py` - CCN: 12, NLOC: 33
8. `_get_db_activity_info@753-794@wks/daemon.py` - CCN: 12, NLOC: 32

### Lower Priority (CCN 11, but high NLOC)
9. `fix_symlinks@34-138@wks/vault/controller.py` - CCN: 11, NLOC: 74
10. `check_path@365-425@wks/monitor/controller.py` - CCN: 11, NLOC: 47
11. `_handle_move_event@378-427@wks/daemon.py` - CCN: 11, NLOC: 33
12. `run@749-777@wks/mcp_server.py` - CCN: 11, NLOC: 23
13. `diff@25-65@wks/diff/controller.py` - CCN: 11, NLOC: 18

### Special Case (Very High NLOC)
14. `__init__@27-309@wks/mcp_server.py` - CCN: 3, NLOC: 282 ⚠️ **This is way over NLOC limit**

## Refactoring Strategy

### General Approach
1. **Extract Methods**: Break large functions into smaller, focused helper methods
2. **Extract Classes**: For very large functions, consider extracting a helper class
3. **Simplify Conditionals**: Use early returns, guard clauses, and strategy patterns
4. **Reduce Nesting**: Flatten deeply nested conditionals

### Specific Patterns

#### For High CCN (Complex Control Flow)
- Extract conditional branches into separate methods
- Use early returns to reduce nesting
- Consider Strategy Pattern for complex branching logic
- Use lookup tables/dictionaries for complex if-elif chains

#### For High NLOC (Long Functions)
- Extract logical sections into helper methods
- Group related operations into private methods
- Consider breaking into multiple smaller public methods
- Extract data processing into separate functions

### Examples from This Campaign

**Before (get_content):**
- CCN: 20, NLOC: 72
- Split into: `_get_content_by_checksum`, `_get_content_by_file_path`, `_copy_cache_file_to_output`, `_find_matching_record_in_db`, `_resolve_cache_file_from_db`
- After: Main method CCN: 2, NLOC: 5

**Before (build_status_rows):**
- CCN: 18, NLOC: 34
- Split into: `_build_health_rows`, `_build_filesystem_rows`, `_build_launch_rows`
- After: Main method CCN: 1, NLOC: 6

## Tasks

### Phase 1: High Priority Violations (CCN >= 14)
1. Fix `get_changes` in `wks/vault/git_watcher.py`
2. Fix `get_changed_since_commit` in `wks/vault/git_watcher.py`
3. Fix `_maybe_flush_pending_deletes` in `wks/daemon.py`
4. Fix `_maybe_prune_monitor_db` in `wks/daemon.py`
5. Fix `_maybe_flush_pending_mods` in `wks/daemon.py`

### Phase 2: Medium Priority (CCN 11-13)
6. Fix `__init__` in `wks/monitor_rules.py`
7. Fix `_read_message` in `wks/mcp_server.py`
8. Fix `_get_db_activity_info` in `wks/daemon.py`

### Phase 3: Lower Priority (CCN 11, high NLOC)
9. Fix `fix_symlinks` in `wks/vault/controller.py`
10. Fix `check_path` in `wks/monitor/controller.py`
11. Fix `_handle_move_event` in `wks/daemon.py`
12. Fix `run` in `wks/mcp_server.py`
13. Fix `diff` in `wks/diff/controller.py`

### Phase 4: Special Cases
14. Fix `__init__` in `wks/mcp_server.py` (NLOC: 282) - This may require significant refactoring

## Success Criteria

- [ ] All functions have CCN <= 10
- [ ] All functions have NLOC <= 100
- [ ] All tests still pass (694 tests)
- [ ] No functionality changes (only refactoring)
- [ ] Code is more maintainable and readable
- [ ] Complexity check passes: `./scripts/check_complexity.py`

## Branch Strategy

1. Create branch from `2025-12-03_linting-baseline`
2. Work through violations systematically (one file at a time)
3. Run tests after each major refactoring
4. Verify complexity after each fix: `lizard -l python -C 10 -L 100 wks`
5. Create PR targeting `2025-12-03_linting-baseline`
6. Wait for Orchestrator review and merge

## Testing Strategy

After each refactoring:
1. Run all tests: `pytest`
2. Run complexity check: `./scripts/check_complexity.py`
3. Run type check: `./scripts/check_types.py`
4. Run format check: `./scripts/check_format.py`

## Notes

- **Preserve Functionality**: Refactoring should not change behavior
- **Maintain Test Coverage**: Ensure all existing tests still pass
- **Follow DRY Principle**: Extract common patterns into reusable helpers
- **Use Type Hints**: Maintain or improve type annotations
- **Document Changes**: Add docstrings to new helper methods
- **Incremental Approach**: Fix one function at a time, test, then move on
- **Ask for Help**: If a function is too complex to refactor safely, ask the Orchestrator for guidance

## Resources

- Project complexity standards: `CONTRIBUTING.md`
- Complexity checking script: `scripts/check_complexity.py`
- Lizard tool documentation: https://github.com/terryyin/lizard
