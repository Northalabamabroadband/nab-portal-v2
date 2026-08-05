#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
python3 -m compileall backend/app
python3 - <<'PY'
from pathlib import Path
required=[Path('frontend/src/main.tsx'),Path('frontend/src/fiberMap.tsx'),Path('backend/app/modules/uisp/client.py'),Path('backend/app/modules/tauc/client.py'),Path('compose.rc1.yml')]
for p in required:
    if not p.exists(): raise SystemExit(f'Missing {p}')
text=Path('frontend/src/fiberMap.tsx').read_text()
assert 'coordinates as [number, number]' in text
print('Static RC1 checks passed.')
PY
if command -v docker >/dev/null 2>&1; then docker compose -f compose.rc1.yml config >/dev/null; fi
echo "RC1 Build 001 validation passed."
