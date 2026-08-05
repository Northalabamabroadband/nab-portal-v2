#!/usr/bin/env bash
set -euo pipefail
BACKUP="${1:-}"
TARGET="${2:-/opt/nab-portal-v2}"
[[ -d "$BACKUP/source" ]] || { echo "Usage: $0 /opt/nab-portal-v2-backups/rc1-build001-TIMESTAMP" >&2; exit 2; }
rm -rf "$TARGET"
cp -a "$BACKUP/source" "$TARGET"
cd "$TARGET"
docker compose -f compose.yml -f compose.milestone3.yml -f compose.milestone5.yml up -d --build
echo "Rollback complete."
