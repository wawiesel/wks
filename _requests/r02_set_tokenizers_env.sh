#!/usr/bin/env bash
# r02: Update WKS LaunchAgent to set TOKENIZERS_PARALLELISM=false and restart service
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[r02] Reinstalling service to apply EnvironmentVariables..."
"$ROOT_DIR/bin/wks-service" install
sleep 2
"$ROOT_DIR/bin/wks-service" status || true

echo "[r02] Done."

