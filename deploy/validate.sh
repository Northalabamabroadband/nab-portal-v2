#!/usr/bin/env bash
set -euo pipefail

python3 -m compileall backend/app
docker compose config >/dev/null

echo "Foundation validation passed."
