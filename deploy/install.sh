#!/usr/bin/env bash
set -euo pipefail

INSTALL_ROOT="${1:-/opt/nab-portal-v2}"

mkdir -p "$INSTALL_ROOT"
cp -a . "$INSTALL_ROOT/"

cd "$INSTALL_ROOT"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created $INSTALL_ROOT/.env"
  echo "Update APP_SECRET_KEY before production use."
fi

docker compose up -d --build
docker compose ps

echo
echo "NAB Portal v2 foundation installed."
echo "Health endpoint: http://127.0.0.1:8200/health"
