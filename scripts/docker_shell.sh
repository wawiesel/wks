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
echo "Image: ${IMAGE_NAME}"
echo "-------------------------------------"

# Detect container runtime
if command -v $DOCKER_CMD &> /dev/null; then
    DOCKER_CMD="$DOCKER_CMD"
elif command -v podman &> /dev/null; then
    DOCKER_CMD="podman"
    echo "ℹ️  Using Podman as container runtime"
else
    echo "❌ Error: No container runtime found ($DOCKER_CMD or podman)"
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
    $DOCKER_CMD exec \
        -u testuser \
        -w /workspace \
        "${CONTAINER_NAME}" \
        bash -c "$CMD"
else
    # Interactive mode (default)
    echo "💻 Dropping into shell as 'testuser'..."
    echo "   (Type 'exit' to quit)"
    echo "-------------------------------------"

    # Enter container with TTY
    $DOCKER_CMD exec -it \
        -u testuser \
        -w /workspace \
        "${CONTAINER_NAME}" \
        bash -c "
            echo 'Welcome to WKS Docker Shell!'
            echo '----------------------------'
            echo 'Check image freshness:'
            ./scripts/check_docker_image.sh -e . --break-system-packages
            echo '----------------------------'
            exec bash
        "
fi
