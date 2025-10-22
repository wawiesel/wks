#!/usr/bin/env bash
# r02: Produce Docling dumps for all Markdown files under include_paths (honors exclude/ignore rules)
# Writes to: ~/obsidian/WKS/Docs/<checksum>.md
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PY="$ROOT_DIR/venv/bin/python"
CFG_FILE="$HOME/.wks/config.json"

if [[ ! -x "$VENV_PY" ]]; then
  echo "[r02] venv python not found at $VENV_PY" >&2
  exit 2
fi
if [[ ! -f "$CFG_FILE" ]]; then
  echo "[r02] config not found at $CFG_FILE" >&2
  exit 2
fi

echo "[r02] Enumerating Markdown files under include_paths..."
MD_LIST="$(mktemp)"
"$VENV_PY" - <<PY
import json, sys
from pathlib import Path
cfg = json.load(open("$CFG_FILE", 'r'))
mon = cfg.get('monitor', {})
incs = [Path(p).expanduser() for p in mon.get('include_paths', [])]
exs = [Path(p).expanduser() for p in mon.get('exclude_paths', [])]
ign_dirs = set(mon.get('ignore_dirnames', []))
def is_within(p, base):
    try:
        p.resolve().relative_to(base.resolve())
        return True
    except Exception:
        return False
def skip_dir(path):
    for part in path.parts:
        if part.startswith('.') and part != '.wks':
            return True
        if part in ign_dirs:
            return True
    return False
def skip_file(p):
    if p.suffix.lower() != '.md':
        return True
    for ex in exs:
        if is_within(p, ex):
            return True
    if skip_dir(p.parent):
        return True
    return False
out = []
for inc in incs:
    if not inc.exists():
        continue
    for p in inc.rglob('*.md'):
        if not skip_file(p):
            out.append(str(p))
print("\n".join(out))
PY
> "$MD_LIST"

COUNT=$(wc -l < "$MD_LIST" | tr -d ' ')
echo "[r02] Found $COUNT Markdown files"
if [[ "$COUNT" -eq 0 ]]; then
  echo "[r02] Nothing to do"
  rm -f "$MD_LIST"
  exit 0
fi

echo "[r02] Indexing Markdown files (this will create docs dumps)..."
while IFS= read -r f; do
  "$VENV_PY" -m wks.cli sim index "$f" >/dev/null 2>&1 || true
done < "$MD_LIST"

rm -f "$MD_LIST"
echo "[r02] Done. Check: $HOME/obsidian/WKS/Docs"

