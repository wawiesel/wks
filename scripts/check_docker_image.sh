#!/bin/bash
# Check if pip install output indicates a stale Docker image

LOG_FILE=$1

if [ -z "$LOG_FILE" ]; then
    echo "Usage: $0 <pip-install-log-file>"
    exit 1
fi

if grep -q "Downloading" "$LOG_FILE" || grep -q "Collecting" "$LOG_FILE"; then
    echo "::error title=Docker Image Stale::Dependencies were downloaded during install! The ci-runner image is out of date."
    echo "::error::Please bump the Docker image version. See docs/testing/ci-runner.md for instructions."
    echo "----------------------------------------------------------------"
    echo "❌ STALE IMAGE DETECTED"
    echo "The Docker image is missing dependencies found in pyproject.toml."
    echo "Dependencies were downloaded during the test run."
    echo "Please bump the version in Dockerfile.ci-runner and workflows."
    echo "See docs/testing/ci-runner.md"
    echo "----------------------------------------------------------------"
    exit 1
else
    echo "✅ Docker image is fresh (no dependencies downloaded)."
    exit 0
fi
