#!/bin/bash
# Print disk available in GB - one-liner for CI diagnostics
# Usage: ./scripts/disk_avail.sh [label]
LABEL="${1:-Disk}"
AVAIL=$(df -BG / 2>/dev/null | awk 'NR==2 {gsub(/G/, "", $4); print $4}' || df -g / | awk 'NR==2 {print $4}')
echo ">>> ${LABEL}: ${AVAIL} GB available"
