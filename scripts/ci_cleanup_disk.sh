#!/bin/bash
# Clean up disk space on GitHub Actions runners
# Usage: ./scripts/ci_cleanup_disk.sh

set -e

echo "Disk usage before cleanup:"
df -h

echo "Removing large unused packages..."
# Android SDKs (~9GB)
if [ -d "/usr/local/lib/android" ]; then
    sudo rm -rf /usr/local/lib/android
fi

# Dotnet (~1GB)
if [ -d "/usr/share/dotnet" ]; then
    sudo rm -rf /usr/share/dotnet
fi

# Haskell / GHC (~1GB)
if [ -d "/opt/ghc" ]; then
    sudo rm -rf /opt/ghc
fi

# CodeQL (~1GB)
if [ -d "/opt/hostedtoolcache/CodeQL" ]; then
    sudo rm -rf /opt/hostedtoolcache/CodeQL
fi

echo "Disk usage after cleanup:"
df -h

# Print summary of available space on root partition
AVAIL_GB=$(df -BG / | awk 'NR==2 {gsub(/G/, "", $4); print $4}')
echo ""
echo "=== SUMMARY: ${AVAIL_GB} GB available on root partition ==="
