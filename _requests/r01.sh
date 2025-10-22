#!/usr/bin/env bash
# r01: One-shot bootstrap for WKS (deps + config + service + smoke tests; optional migrate)
# Usage:
#   _requests/r01.sh             # install deps, write config, install service, smoke test
#   _requests/r01.sh migrate     # same as above, then migrate all embeddings

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT_DIR/venv"
VENV_PY="$VENV/bin/python"
VENV_PIP="$VENV/bin/pip"
CFG_DIR="$HOME/.wks"
CFG_FILE="$CFG_DIR/config.json"

echo "[r01] Root: $ROOT_DIR"

# 1) Ensure venv + deps
if [[ ! -x "$VENV_PY" ]]; then
  echo "[r01] Creating venv at $VENV"
  python3 -m venv "$VENV"
fi
echo "[r01] Upgrading pip/wheel"
"$VENV_PIP" install --upgrade pip wheel
echo "[r01] Installing WKS (editable)"
"$VENV_PIP" install -e .
echo "[r01] Installing docling"
"$VENV_PIP" install docling || {
  echo "[r01] WARNING: failed to install docling; extraction may fail if engine=docling" >&2
}

echo "[r01] Dependency sanity checks:"
"$VENV_PY" - <<'PY'
import sys
print('python:', sys.executable)
try:
    import watchdog, pymongo
    print('watchdog/pymongo OK')
except Exception as e:
    print('watchdog/pymongo missing:', e)
try:
    from sentence_transformers import SentenceTransformer
    print('sentence-transformers OK')
except Exception as e:
    print('sentence-transformers missing:', e)
try:
    import docling
    print('docling OK')
except Exception as e:
    print('docling missing:', e)
PY

# 2) Write explicit config (backup if present)
mkdir -p "$CFG_DIR"
if [[ -f "$CFG_FILE" ]]; then
  cp "$CFG_FILE" "$CFG_FILE.bak.$(date +%s)"
fi

cat > "$CFG_FILE" <<'JSON'
{
  "vault_path": "~/obsidian",
  "monitor": {
    "include_paths": ["~"],
    "exclude_paths": ["~/Library", "~/obsidian", "~/.wks"],
    "ignore_dirnames": [
      "node_modules","venv",".venv","__pycache__","build","_build","dist","Applications",".cache","Cache","Caches"
    ],
    "ignore_globs": ["**/.DS_Store","*.swp","*.tmp","*~","._*","~$*",".~lock.*#"],
    "state_file": "~/.wks/monitor_state.json"
  },
  "activity": {
    "state_file": "~/.wks/activity_state.json"
  },
  "obsidian": {
    "base_dir": "WKS",
    "log_max_entries": 500,
    "active_files_max_rows": 50,
    "source_max_chars": 40,
    "destination_max_chars": 40,
    "docs_keep": 99
  },
  "similarity": {
    "enabled": true,
    "mongo_uri": "mongodb://localhost:27027/",
    "database": "wks_similarity",
    "collection": "file_embeddings",
    "model": "all-MiniLM-L6-v2",
    "include_extensions": [".md",".txt",".py",".ipynb",".tex"],
    "min_chars": 10,
    "max_chars": 200000,
    "chunk_chars": 1500,
    "chunk_overlap": 200
  },
  "extract": {
    "engine": "docling",
    "ocr": false,
    "timeout_secs": 30
  }
}
JSON

echo "[r01] Wrote config $CFG_FILE"

# 3) Install/start service (MongoDB + WKS)
"$ROOT_DIR/bin/wks-service" install
sleep 2
"$ROOT_DIR/bin/wks-service" status || true

# 4) Smoke test: extract + index + stats + docs listing
echo "[r01] Extraction test (README.md):"
"$VENV_PY" -m wks.cli sim extract --path "$ROOT_DIR/README.md" || true

echo "[r01] Indexing README.md and SPEC.md:"
"$VENV_PY" -m wks.cli sim index "$ROOT_DIR/README.md" "$ROOT_DIR/SPEC.md" || true

echo "[r01] DB stats:"
"$VENV_PY" -m wks.cli sim stats || true

echo "[r01] Query similar to README.md:"
"$VENV_PY" -m wks.cli sim query --path "$ROOT_DIR/README.md" --mode chunk --top 5 || true

echo "[r01] Docling dumps for Markdown files (full scan):"
"$VENV_PY" -m wks.cli sim dump-docs || true
echo "[r01] Docs folder contents:"
ls -la "$HOME/obsidian/WKS/Docs" || true

# 5) Optional migrate
if [[ "${1:-}" == "migrate" ]]; then
  echo "[r01] Migrating embeddings across DB..."
  "$VENV_PY" -m wks.cli sim migrate --prune-missing --json || true
fi

echo "[r01] Done."
