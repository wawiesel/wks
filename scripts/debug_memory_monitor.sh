#!/bin/bash
# Debug memory monitor - logs top 3 RSS consumers every second
# Enable with: DEBUG_MEMORY=true in CI environment
#
# Usage: ./scripts/debug_memory_monitor.sh [log_file]
#   log_file: Path to write memory log (default: /tmp/memory.log)

LOG_FILE="${1:-/tmp/memory.log}"

while true; do
  ts=$(date +%H:%M:%S)
  # Get top 3 RSS consumers with numeric values
  top3=$(ps -eo rss=,args= --sort=-rss 2>/dev/null | head -3 | while read rss args; do
    mb=$((rss / 1024))
    echo "${mb}MB ${args:0:40}"
  done | tr "\n" " | ")
  echo "$ts $top3" >> "$LOG_FILE"
  sleep 1
done
