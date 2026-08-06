#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_FILE="$ROOT/compose.rc1.yml"
BACKUP_DIR="$ROOT/backups"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"

cd "$ROOT"
bash deploy/preflight-rc1.sh

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

if docker inspect nab-v2-postgres >/dev/null 2>&1; then
  BACKUP_FILE="$BACKUP_DIR/nab-portal-${STAMP}.dump"
  printf 'Creating PostgreSQL backup: %s\n' "$BACKUP_FILE"
  docker exec nab-v2-postgres pg_dump -U nab_portal -d nab_portal -Fc > "$BACKUP_FILE"
  [ -s "$BACKUP_FILE" ] || {
    rm -f "$BACKUP_FILE"
    printf 'Database backup was empty; deployment stopped.\n' >&2
    exit 1
  }
fi

printf 'Building RC1 containers...\n'
docker compose -f "$COMPOSE_FILE" build

printf 'Starting RC1 containers...\n'
docker compose -f "$COMPOSE_FILE" up -d --remove-orphans

for attempt in $(seq 1 36); do
  API_STATUS="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' nab-v2-api 2>/dev/null || true)"
  POSTGRES_STATUS="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' nab-v2-postgres 2>/dev/null || true)"
  REDIS_STATUS="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' nab-v2-redis 2>/dev/null || true)"
  WEB_STATUS="$(docker inspect --format '{{.State.Status}}' nab-v2-web 2>/dev/null || true)"

  if [ "$API_STATUS" = "healthy" ] && [ "$POSTGRES_STATUS" = "healthy" ] && [ "$REDIS_STATUS" = "healthy" ] && [ "$WEB_STATUS" = "running" ]; then
    printf 'Deployment healthy: API, PostgreSQL, Redis, and web are ready.\n'
    docker compose -f "$COMPOSE_FILE" ps
    exit 0
  fi

  sleep 5
done

printf 'Deployment did not become healthy in time. Current state:\n' >&2
docker compose -f "$COMPOSE_FILE" ps >&2
printf '\nPostgreSQL logs:\n' >&2
docker logs --tail 60 nab-v2-postgres >&2 || true
printf '\nAPI logs:\n' >&2
docker logs --tail 60 nab-v2-api >&2 || true
exit 1
