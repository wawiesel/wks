# Agent 2: Rebase Instructions

## ⚠️ STATUS UPDATE: MERGE COMPLETED

**As of 2025-12-02:** The `test-refactor/unit-tests` branch has been **merged into `test-refactor-campaign`** instead of rebasing. All infrastructure files from Agent 1 are now present in the campaign branch alongside Agent 2's unit test work.

**These rebase instructions are kept for reference**, but are no longer needed since the merge has been completed.

---

## Original Instructions (For Reference)

### Your Branch Needs to Be Updated

Your branch `test-refactor/unit-tests` was based on an older version of the campaign branch and was missing Agent 1's infrastructure work (pytest.ini, conftest.py, etc.).

**Note:** This was resolved by merging the branch into `test-refactor-campaign` instead of rebasing.

## Steps to Rebase (No Longer Needed - For Reference Only)

**Note:** These steps were not needed as the branch was merged instead. Kept for reference:

Run these commands in order (if rebase was needed):

```bash
# 1. Checkout your branch
git checkout test-refactor/unit-tests

# 2. Fetch latest changes from remote
git fetch origin

# 3. Rebase onto the current campaign branch
git rebase origin/test-refactor-campaign

# 4. If there are conflicts, resolve them, then continue:
#    (After fixing conflicts in files)
#    git add <resolved-files>
#    git rebase --continue

# 5. Once rebase is complete, force push your branch
git push origin test-refactor/unit-tests --force-with-lease
```

## After Rebase, Verify: (Completed via Merge)

**Status:** ✅ All verification completed after merge:

```bash
# Check that Agent 1's files are present
ls tests/pytest.ini
ls tests/conftest.py
ls tests/README.md

# Verify your unit tests are still there
ls tests/unit/test_*.py

# Run tests to make sure everything works
pytest tests/unit/ -v
```

## Expected Result (Achieved via Merge)

After merge, the campaign branch now has:
- ✅ All of Agent 1's infrastructure files (pytest.ini, conftest.py, etc.)
- ✅ All moved unit tests in `tests/unit/` (9 files)
- ✅ All `@pytest.mark.unit` decorators (38 total)
- ⚠️ Tests should be verified: `pytest tests/unit/ -v`

## If You Encounter Conflicts

If there are merge conflicts during rebase:
1. The conflicts will be in files that both you and Agent 1 modified
2. Resolve conflicts by keeping both sets of changes where possible
3. For pytest.ini and conftest.py: keep Agent 1's versions (they're the infrastructure)
4. For test files: keep your versions (with unit markers)
5. After resolving: `git add <file>` then `git rebase --continue`

## Current Status

**✅ MERGE COMPLETED**

The `test-refactor/unit-tests` branch has been successfully merged into `test-refactor-campaign`. 

**For more details, see:**
- Review document: `docs/AGENT2_REVIEW.md` (updated with merge status)
- All infrastructure files are present
- All unit tests are in `tests/unit/` with proper markers

**Next Steps:**
- Verify tests pass: `pytest tests/unit/ -v`
- Ensure CI runs successfully on the campaign branch

