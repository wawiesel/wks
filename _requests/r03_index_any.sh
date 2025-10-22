#!/usr/bin/env bash
# r03: Index a file from anywhere. Ensures its extension is allowed, restarts service, then indexes.
# Usage: _requests/r03_index_any.sh "/absolute/path/to/file.ext"
set -euo pipefail

FILE_PATH="${1:-}"
if [[ -z "$FILE_PATH" ]]; then
  echo "Usage: $0 /absolute/path/to/file.ext" >&2
  exit 2
fi
if [[ ! -f "$FILE_PATH" ]]; then
  echo "No such file: $FILE_PATH" >&2
  exit 2
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PY="$ROOT_DIR/venv/bin/python"
CFG_FILE="$HOME/.wks/config.json"
EXT="$(echo "${FILE_PATH##*.}" | tr 'A-Z' 'a-z')"
EXT_DOT=".${EXT}"

if [[ ! -x "$VENV_PY" ]]; then
  echo "venv not found at $VENV_PY" >&2
  exit 2
fi
if [[ ! -f "$CFG_FILE" ]]; then
  echo "Config not found at $CFG_FILE" >&2
  exit 2
fi

echo "[r03] Ensuring extension $EXT_DOT is allowed in similarity.include_extensions..."
export CFG_FILE EXT_DOT
python3 - <<PY
import json, os
from pathlib import Path
cfg_path = Path(os.getenv('CFG_FILE',''))
ext = os.getenv('EXT_DOT','')
if not cfg_path:
    print('Fatal: CFG_FILE not set in environment')
    raise SystemExit(2)
if not ext:
    print('Fatal: EXT_DOT not set in environment')
    raise SystemExit(2)
cfg = json.load(open(cfg_path,'r'))
sim = cfg.get('similarity')
if sim is None or 'include_extensions' not in sim:
    print("Fatal: similarity.include_extensions missing")
    raise SystemExit(2)
lst = [e.lower() for e in sim['include_extensions']]
if ext not in lst:
    lst.append(ext)
    sim['include_extensions'] = lst
    json.dump(cfg, open(cfg_path,'w'), indent=2)
    print('UPDATED')
else:
    print('UNCHANGED')
PY

echo "[r03] Restarting service (Mongo + WKS)..."
"$ROOT_DIR/bin/wks-service" restart
sleep 2
"$ROOT_DIR/bin/wks-service" status || true

echo "[r03] Indexing: $FILE_PATH"
"$VENV_PY" -m wks.cli sim index "$FILE_PATH" || true

echo "[r03] Recent Docs:"
ls -lt "$HOME/obsidian/WKS/Docs" 2>/dev/null | head -n 10 || echo "(no docs yet)"

echo "[r03] Done."
