# CI Docker Image

- `ci-runner:v1`

## Contract

- The CI container is the source of truth for the Linux test environment.
- Dependencies must already exist in the image.
- `pip install -e . --break-system-packages` inside the container should be a null-op except for the editable wheel build.
- If CI starts downloading packages, the image is stale and must be bumped.

## Bump the Image

Bump `v1 -> v2` when:

- `pyproject.toml` or install dependencies change
- `docker/Dockerfile.ci-runner` changes system packages
- CI needs a different runtime baseline

Update the tag in:

- `.github/workflows/publish-ci-image.yml`
- `.github/workflows/test.yml`
- `docker/README.md`

## Local Checks

Build:

```bash
docker build -f docker/Dockerfile.ci-runner -t ci-runner:v1 .
```
Open a shell with systemd:

```bash
./scripts/docker_shell.sh docker
# or
./scripts/docker_shell.sh podman
```

Once inside, run the same commands as CI:

```bash
pip3 install -e . --break-system-packages
python3 -m pytest tests/smoke/ -v
python3 -m pytest tests/ -v
```
