# CI Error Handling Guide

## How to Handle CI Failures

### 1. Identify the Failure

**Check the GitHub Actions logs:**
- Go to: https://github.com/wawiesel/wks/actions
- Click on the failing workflow run
- Click on the failing job to see detailed logs
- Look for error messages (usually in red) at the bottom of the output

### 2. Common CI Failure Types

#### A. Test Failures
**Symptoms:** Tests fail during `pytest tests/ -v`

**Solutions:**
- Run tests locally first: `pytest tests/ -v`
- Check if the failure is specific to CI environment
- Verify all dependencies are installed correctly
- Check if tests require external services (MongoDB, filesystem) that aren't available in CI

**Fix in workflow:** Add pytest markers to skip tests that require external services:
```yaml
- name: Run tests
  run: |
    python -m pytest tests/ -v --tb=short -m "not slow and not requires_mongodb"
```

#### B. Import Errors
**Symptoms:** `ModuleNotFoundError` or `ImportError`

**Solutions:**
- Verify `setup.py` includes all required dependencies
- Check if imports are relative vs absolute
- Ensure `__init__.py` files exist in package directories

#### C. Dependency Installation Failures
**Symptoms:** `pip install -e .` fails

**Solutions:**
- Check `setup.py` syntax
- Verify all dependencies are listed in `install_requires`
- Check if dependencies are available on PyPI

#### D. Python Version Issues
**Symptoms:** Works locally but fails in CI for specific Python versions

**Solutions:**
- Test locally with multiple Python versions: `pyenv local 3.10 3.11 3.12`
- Check for Python version-specific code (e.g., `match/case` requires 3.10+)
- Use `sys.version_info` checks for version-specific code

### 3. Make CI More Robust

#### Add Continue-on-Error for Non-Critical Steps

```yaml
- name: Run tests
  continue-on-error: true  # Don't fail the job if tests fail
  run: |
    python -m pytest tests/ -v --tb=short
```

#### Add Caching for Dependencies

```yaml
- name: Cache pip packages
  uses: actions/cache@v3
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ hashFiles('**/setup.py') }}
    restore-keys: |
      ${{ runner.os }}-pip-
```

#### Add Retry Logic

```yaml
- name: Run tests with retry
  uses: nick-invision/retry@v2
  with:
    timeout_minutes: 10
    max_attempts: 3
    command: python -m pytest tests/ -v --tb=short
```

### 4. Debug CI Locally

#### Use act (GitHub Actions locally)

```bash
# Install act
brew install act  # macOS
# or
curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash

# Run workflow locally
act -j test
```

#### Reproduce CI Environment Locally

```bash
# Use Docker to match CI environment
docker run -it --rm ubuntu:latest bash
apt-get update && apt-get install -y python3.10 python3-pip
# Then run your tests
```

### 5. Quick Fixes for Common Issues

#### If tests fail due to missing pytest.ini:
```bash
# Ensure pytest.ini is committed
git add tests/pytest.ini
git commit -m "Add pytest.ini for CI"
```

#### If conftest.py causes issues:
```bash
# Check for syntax errors
python -c "import ast; ast.parse(open('tests/conftest.py').read())"
```

#### If import paths break:
```bash
# Test imports
python -c "import sys; sys.path.insert(0, '.'); import wks"
```

### 6. Update Workflow for Better Error Reporting

Add job outputs and better error messages:

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - name: Run tests
        id: test
        run: |
          python -m pytest tests/ -v --tb=short || echo "::error::Tests failed"
          exit 1
      - name: Upload test results
        if: failure()
        uses: actions/upload-artifact@v3
        with:
          name: test-results
          path: test-results.xml
```

### 7. For Campaign Branches

**Current Issue:** CI only runs on `master` and `main` branches.

**Options:**

#### Option A: Add campaign branches to CI
```yaml
on:
  push:
    branches: [ master, main, test-refactor-campaign ]
  pull_request:
    branches: [ master, main, test-refactor-campaign ]
```

#### Option B: Use workflow_dispatch for manual runs
```yaml
on:
  workflow_dispatch:
    inputs:
      branch:
        description: 'Branch to test'
        required: true
        default: 'master'
```

#### Option C: Run CI on all branches (may be too noisy)
```yaml
on:
  push:
    branches: ['**']  # All branches
```

### 8. Immediate Actions for Current Failure

1. **Check which branch CI is testing:**
   - If it's testing master, check if Agent 1's changes were merged
   - If it's testing a PR, check what's in that PR

2. **Check the actual error in logs:**
   - Copy the error message from GitHub Actions
   - Search for similar issues in the codebase

3. **Reproduce locally:**
   ```bash
   git checkout <branch-that-failed>
   pip install -e .
   pytest tests/ -v
   ```

4. **Fix and push:**
   - Make the fix
   - Push to the branch
   - CI will re-run automatically

### 9. Prevention

- **Always test locally before pushing:**
  ```bash
  pip install -e .
  pytest tests/ -v
  ```

- **Use pre-commit hooks:**
  ```bash
  pip install pre-commit
  pre-commit install
  ```

- **Run CI-like tests locally:**
  ```bash
  # Use the same commands CI uses
  python -m pytest tests/ -v --tb=short
  ```

---

## Need Help?

If you can't resolve the CI error:
1. Copy the exact error message from GitHub Actions logs
2. Check which commit/branch is failing
3. Check if it's a transient issue (network, GitHub outage)
4. Check GitHub Status: https://www.githubstatus.com/

