#!/bin/bash
# scripts/docker_shell.sh
# Launch a shell inside the CI container with systemd enabled.

set -e

# Configuration
IMAGE_NAME="ghcr.io/wawiesel/wks/ci-runner:v1"
CONTAINER_NAME="wks-ci-shell"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "🚀 Starting WKS Docker Environment..."
echo "-------------------------------------"

# Check if container is already running
if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "✅ Container '${CONTAINER_NAME}' needs restart..."
    docker rm -f "${CONTAINER_NAME}" > /dev/null
fi

# Cleanup existing stopped container
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    docker rm "${CONTAINER_NAME}" > /dev/null
fi

echo "📦 Running container..."
docker run -d \
    --name "${CONTAINER_NAME}" \
    --privileged \
    --cgroupns=host \
    --tmpfs /run \
    --tmpfs /run/lock \
    -v /sys/fs/cgroup:/sys/fs/cgroup:rw \
    -v "${REPO_ROOT}:/workspace" \
    -w /workspace \
    "${IMAGE_NAME}" \
    /lib/systemd/systemd > /dev/null

echo "⏳ Waiting for systemd..."
sleep 2

# Trap to kill container on exit
cleanup() {
    echo ""
    echo "🛑 Stopping container..."
    docker kill "${CONTAINER_NAME}" > /dev/null
    docker rm "${CONTAINER_NAME}" > /dev/null
    echo "Done."
}
trap cleanup EXIT

echo "💻 Dropping into shell as 'testuser'..."
echo "   (Type 'exit' to quit)"
echo "-------------------------------------"

# Enter container
docker exec -it \
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
