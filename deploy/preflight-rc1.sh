#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_FILE="$ROOT/compose.rc1.yml"
MIN_FREE_KB="${MIN_FREE_KB:-2097152}"

fail() {
  printf 'Preflight failed: %s\n' "$1" >&2
  exit 1
}

command -v docker >/dev/null 2>&1 || fail "Docker is not installed."
docker compose version >/dev/null 2>&1 || fail "Docker Compose is unavailable."
[ -f "$COMPOSE_FILE" ] || fail "compose.rc1.yml is missing."
[ -f "$ROOT/.env" ] || fail ".env is missing; production configuration was not changed."

AVAILABLE_KB="$(df -Pk "$ROOT" | awk 'NR==2 {print $4}')"
[ -n "$AVAILABLE_KB" ] || fail "Unable to determine available disk space."
if [ "$AVAILABLE_KB" -lt "$MIN_FREE_KB" ]; then
  AVAILABLE_MB="$((AVAILABLE_KB / 1024))"
  fail "Only ${AVAILABLE_MB} MB is free. At least 2048 MB is required before a Docker build."
fi

docker compose -f "$COMPOSE_FILE" config --quiet || fail "Compose configuration is invalid."

if docker inspect nab-v2-postgres >/dev/null 2>&1; then
  POSTGRES_STATUS="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' nab-v2-postgres)"
  [ "$POSTGRES_STATUS" = "healthy" ] || fail "PostgreSQL is ${POSTGRES_STATUS}; deployment stopped before changing containers."
fi

printf 'Preflight passed: %s MB free, Compose valid, database protected.\n' "$((AVAILABLE_KB / 1024))"
