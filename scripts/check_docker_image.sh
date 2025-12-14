#!/bin/bash
# Wrapper for pip install to check for stale Docker image
# Usage: ./scripts/check_docker_image.sh [pip install args...]

# Create a temp file for log
LOG_FILE=$(mktemp)

# Run the command passed as arguments, pipe to tee to show output while capturing
echo "Running: pip3 install $*"
pip3 install "$@" 2>&1 | tee "$LOG_FILE"
PIP_EXIT_CODE=${PIPESTATUS[0]}

# If pip failed, exit with its code
if [ $PIP_EXIT_CODE -ne 0 ]; then
    rm "$LOG_FILE"
    exit $PIP_EXIT_CODE
fi

# Check for indicators of downloading
if grep -q "Downloading" "$LOG_FILE" || grep -q "Collecting" "$LOG_FILE"; then
    echo ""
    echo "----------------------------------------------------------------"
    echo "❌ STALE DOCKER IMAGE DETECTED"
    echo "Dependencies were downloaded during install."
    echo "This means the CI runner image is out of date with pyproject.toml."
    echo "Please bump the version in 'docker/Dockerfile.ci-runner'."
    echo "See docs/testing/ci-runner.md for instructions."
    echo "----------------------------------------------------------------"
    echo "::error title=Docker Image Stale::Dependencies were downloaded! The ci-runner image is out of date."

    rm "$LOG_FILE"
    # We exit 0 because the build technically succeeded (deps installed),
    # but we've warned the user.
    # User can decide if they want to fail on stale image by checking the annotation.
    exit 0
else
    echo "✅ Docker image is fresh (no dependencies downloaded)."
    rm "$LOG_FILE"
    exit 0
fi
