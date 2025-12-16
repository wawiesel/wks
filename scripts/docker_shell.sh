#!/bin/bash
# scripts/docker_shell.sh
# Launch a shell inside the CI container with systemd enabled.

set -e

# Configuration
# Configuration
IMAGE_NAME="${IMAGE_NAME:-ghcr.io/wawiesel/wks/ci-runner:v1}"
CONTAINER_NAME="wks-ci-shell"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "🚀 Starting WKS Docker Environment..."
echo "Image: ${IMAGE_NAME}"
echo "-------------------------------------"

# Argument parsing: Check if first argument is a known runtime
if [[ "$1" == "docker" || "$1" == "podman" ]]; then
    DOCKER_CMD="$1"
    shift
    echo "⚙️  Runtime explicitly set to: $DOCKER_CMD"
else
    echo "❌ Error: You must specify the container runtime."
    echo "Usage: ./scripts/docker_shell.sh [docker|podman] [command]"
    exit 1
fi

# Check if container is already running
if $DOCKER_CMD ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "✅ Container '${CONTAINER_NAME}' needs restart..."
    $DOCKER_CMD rm -f "${CONTAINER_NAME}" > /dev/null
fi

# Cleanup existing stopped container
if $DOCKER_CMD ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    $DOCKER_CMD rm "${CONTAINER_NAME}" > /dev/null
fi

echo "📦 Running container..."
$DOCKER_CMD run -d \
    --name "${CONTAINER_NAME}" \
    --platform linux/amd64 \
    --privileged \
    --cgroupns=host \
    --tmpfs /run \
    --tmpfs /run/lock \
    -v /sys/fs/cgroup:/sys/fs/cgroup:rw \
    -v "${REPO_ROOT}:/workspace" \
    -w /workspace \
    -e GITHUB_ACTIONS="${GITHUB_ACTIONS}" \
    "${IMAGE_NAME}" \
    /lib/systemd/systemd > /dev/null

echo "⏳ Waiting for systemd..."
sleep 2

# Trap to kill container on exit
cleanup() {
    EXIT_CODE=$?
    echo ""
    echo "🛑 Stopping container..."
    $DOCKER_CMD kill "${CONTAINER_NAME}" > /dev/null
    $DOCKER_CMD rm "${CONTAINER_NAME}" > /dev/null
    echo "Done."
    exit $EXIT_CODE
}
trap cleanup EXIT

CMD="$@"

if [ -n "$CMD" ]; then
    # Non-interactive mode (for CI or direct commands)
    echo "🔌 Executing command in container: $CMD"
    echo "-------------------------------------"
    # We don't use -t to avoid TTY control characters in logs unless needed
    # We pass the command to bash -c
    # We pass the command to bash -c via the wrapper
    $DOCKER_CMD exec -u testuser \
        "${CONTAINER_NAME}" \
        bash -c "$CMD"
else
    # Interactive mode (default)
    echo "💻 Dropping into shell as 'testuser'..."
    echo "   (Type 'exit' to quit)"
    echo "-------------------------------------"

    # Enter container with TTY using wrapper
    $DOCKER_CMD exec -it -u testuser \
        "${CONTAINER_NAME}" \
        bash -c "
            echo 'Welcome to WKS Docker Shell!'
            echo '----------------------------'
            echo 'Environment ready.'
            echo '----------------------------'
            exec bash
        "
fi
