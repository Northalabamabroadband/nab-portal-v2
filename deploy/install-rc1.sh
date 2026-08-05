#!/usr/bin/env bash
set -euo pipefail
SOURCE="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="${1:-/opt/nab-portal-v2}"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="/opt/nab-portal-v2-backups/rc1-build001-$STAMP"
mkdir -p "$BACKUP"
if [[ -d "$TARGET" ]]; then
  cp -a "$TARGET" "$BACKUP/source"
fi
ENV_TMP="$(mktemp)"
if [[ -f "$TARGET/.env" ]]; then cp "$TARGET/.env" "$ENV_TMP"; fi
mkdir -p "$TARGET"
rsync -a --delete --exclude '.env' --exclude 'secrets/' "$SOURCE/" "$TARGET/"
if [[ -s "$ENV_TMP" ]]; then cp "$ENV_TMP" "$TARGET/.env"; elif [[ ! -f "$TARGET/.env" ]]; then cp "$TARGET/.env.example" "$TARGET/.env"; fi
mkdir -p "$TARGET/secrets/tauc"
chmod +x "$TARGET/deploy/"*.sh
cd "$TARGET"
./deploy/validate-rc1.sh
docker compose -f compose.rc1.yml build --no-cache api web
docker compose -f compose.rc1.yml up -d --force-recreate
sleep 10
curl -fsS http://127.0.0.1:8200/health; echo
curl -fsS http://127.0.0.1:8300/health; echo
echo "RC1 Build 001 installed. Backup: $BACKUP"
