# CI Docker Image Versioning

## Current Version: v1

The CI pipeline uses a pre-built Docker image (`ci-runner:v1`) with all project dependencies pre-installed. This ensures fast test runs and makes dependency installation during CI a null-op.

## Architecture

### Image Contents
The Docker image contains:
- Ubuntu 24.04 base with systemd support
- MongoDB 7.0 server
- Python 3.x with all dependencies from `pyproject.toml` pre-installed
- Test frameworks (pytest, coverage, mutation testing)
- Linting tools (ruff, mypy)

### Dependency Installation Strategy
During the Docker image build:
1. Copy `pyproject.toml`, `setup.py`, `setup.cfg` into image
2. Run `pip install .` to install ALL dependencies
3. Remove copied files (source code is mounted at runtime)

During CI test runs:
```bash
pip install -e . --no-deps --break-system-packages
```

This installs ONLY the `wks` package itself (editable) without downloading any dependencies, since they're already in the image.

## When to Bump Version

**You MUST bump the version (v1 → v2) when**:
- Adding new dependencies to `pyproject.toml` or `setup.py`
- Removing dependencies
- Upgrading major versions of dependencies
- Changing system packages in `Dockerfile.ci-runner`

**Red Flag**: If you see pip downloading packages during CI runs, the image is stale and needs a version bump.

## How to Bump Version

### Step 1: Create a Version Bump PR

Create a new branch and PR specifically for the version bump:

```bash
git checkout -b chore/bump-ci-image-v2
```

### Step 2: Update Version References

Update the version in these files:

1. **`.github/workflows/publish-ci-image.yml`** (line 40):
   ```yaml
   tags: |
     type=raw,value=v2  # Change from v1 to v2
     type=raw,value=latest
   ```

2. **`.github/workflows/test.yml`** (3 locations):
   - Line 34: `ghcr.io/${REPO_LOWER}/ci-runner:v2`
   - Line 85: `docker pull ghcr.io/${REPO_LOWER}/ci-runner:v2`
   - Line 99: `ghcr.io/${REPO_LOWER}/ci-runner:v2`

3. **`docs/CI_DOCKER_IMAGE.md`** (this file):
   - Line 3: `## Current Version: v2`

### Step 3: Commit and Push

```bash
git add .github/workflows/publish-ci-image.yml .github/workflows/test.yml docs/CI_DOCKER_IMAGE.md
git commit -m "chore: bump CI Docker image to v2"
git push origin chore/bump-ci-image-v2
```

### Step 4: Open PR and Wait for Image Build

1. Open PR on GitHub
2. The `Publish CI Docker Image` workflow will trigger automatically
3. Wait for the workflow to complete - this builds and publishes `ci-runner:v2`
4. The PR's test workflow will use the new `v2` image

### Step 5: Merge After Tests Pass

Once all tests pass using the new `v2` image, merge the PR.

## Testing Image Locally

### Build the Image

```bash
docker build -f Dockerfile.ci-runner -t ci-runner:v1 .
```

This will take 10-15 minutes due to downloading heavy dependencies like `sentence-transformers` and `docling`.

### Verify Dependencies Are Pre-installed

```bash
docker run --rm ci-runner:v1 pip3 list
```

Should show all dependencies including:
- `sentence-transformers`
- `docling`
- `pymongo`
- `pytest`
- etc.

### Test Null-op Installation

```bash
docker run --rm \
  -v $(pwd):/workspace \
  -w /workspace \
  ci-runner:v1 \
  bash -c "pip3 install -e . --no-deps --break-system-packages 2>&1 | tee /tmp/install.log && cat /tmp/install.log"
```

**Expected output**:
```
Obtaining file:///workspace
  Installing build dependencies ... done
  Checking if build backend supports build_editable ... done
  Getting requirements to build editable ... done
  Preparing editable metadata (pyproject.toml) ... done
Building wheels for collected packages: wks
  Building editable for wks (pyproject.toml) ... done
Successfully built wks
Installing collected packages: wks
Successfully installed wks-0.5.0
```

**No "Downloading" or "Collecting" messages should appear** - if they do, dependencies are missing from the image.

### Run Smoke Tests

```bash
docker run --rm \
  -v $(pwd):/workspace \
  -w /workspace \
  ci-runner:v1 \
  bash -c "pip3 install -e . --no-deps --break-system-packages && python3 -m pytest tests/smoke/ -v"
```

### Run Full Test Suite

```bash
docker run --rm \
  --privileged \
  --cgroupns=host \
  --tmpfs /run \
  --tmpfs /run/lock \
  -v /sys/fs/cgroup:/sys/fs/cgroup:rw \
  -v $(pwd):/workspace \
  -w /workspace \
  ci-runner:v1 \
  bash -c "
    /lib/systemd/systemd --system &
    sleep 2
    sudo -u testuser bash -c 'cd /workspace && pip3 install --user --no-deps -e . --break-system-packages'
    sudo -u testuser bash -c 'cd /workspace && python3 -m pytest tests/ -v --tb=short'
  "
```

## Troubleshooting

### CI Shows "Downloading" Messages

**Problem**: Dependencies are being downloaded during CI runs.

**Solution**: The image is out of sync with `pyproject.toml`. Bump the version following the steps above.

### Build Fails with "No space left on device"

**Problem**: Heavy dependencies (especially ML libraries) take up significant space.

**Solution**: This is expected during image build. GitHub Actions has enough space for building the image, but not for running `pip install .` twice (which is why we use `--no-deps` at runtime).

### Tests Fail After Version Bump

**Problem**: New dependency versions may have breaking changes.

**Solution**:
1. Check if dependency version constraints need updating in `pyproject.toml`
2. Review test failures to see if they're related to dependency changes
3. May need to update test code to work with new dependency versions

## Version History

- **v1** (2025-12-14): Initial versioned release
  - Based on Ubuntu 24.04
  - Python 3.12
  - MongoDB 7.0
  - All dependencies from `pyproject.toml` pre-installed
