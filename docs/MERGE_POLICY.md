# Merge Policy: No Merges Without Passing CI

## Policy

**NEVER merge a pull request without all CI tests passing.**

## Requirements Before Merging

### 1. CI Must Run ✅
- GitHub Actions workflow must have executed
- Check the "Checks" tab on the PR
- Look for "Tests" workflow status

### 2. All Tests Must Pass ✅
- All pytest tests must pass: `pytest tests/ -v`
- All Python versions (3.10, 3.11, 3.12) must pass
- No failing test jobs in CI

### 3. Required Checks ✅
- All required status checks must be green
- No skipped tests (unless intentionally skipped with `@pytest.mark.skip`)
- Import checks must pass

## How to Verify

### Before Merging a PR:

1. **Check PR Status:**
   ```
   - Go to PR page
   - Look at "Checks" tab
   - Verify all jobs show green ✓
   ```

2. **If CI hasn't run:**
   - Check if workflow file is correct
   - Manually trigger workflow if needed (workflow_dispatch)
   - Wait for CI to complete before merging

3. **If CI is failing:**
   - DO NOT merge
   - Fix the failing tests
   - Push fixes and wait for CI to pass
   - Only merge after all checks pass

## CI Configuration

The workflow file (`.github/workflows/test.yml`) is configured to:
- Run on all PRs targeting `master` or `main`
- Run on pushes to `master` or `main`
- Test against Python 3.10, 3.11, and 3.12
- Fail fast if any tests fail (`continue-on-error: false`)

## Enforcement

- **Code Review:** All reviewers must verify CI passes before approving
- **Branch Protection:** If configured, GitHub will block merges with failing CI
- **Team Responsibility:** Everyone must ensure CI passes before merging

## Troubleshooting

### CI didn't run?
1. Check if workflow file exists in base branch (master)
2. Verify `pull_request:` trigger is configured correctly
3. Check GitHub Actions tab for workflow runs

### CI is failing?
1. Review test failures in CI logs
2. Reproduce locally: `pytest tests/ -v`
3. Fix failing tests
4. Push fixes and wait for CI to pass

### Need to bypass CI? (NOT RECOMMENDED)
- Only in emergency situations
- Must have explicit approval
- Must follow up immediately to fix issues

---

**Remember: Green CI = Safe to Merge. Red CI = DO NOT MERGE.**

