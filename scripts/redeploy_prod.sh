#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
BACKEND_IMAGE_NAME="${BACKEND_IMAGE_NAME:-ptnk-chatbot-backend}"

if ! command -v docker >/dev/null 2>&1; then
  echo "Khong tim thay lenh docker. Hay cai Docker truoc."
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "Khong tim thay docker compose plugin. Hay cai docker-compose-v2 truoc."
  exit 1
fi

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "Khong tim thay file compose: $COMPOSE_FILE"
  exit 1
fi

if [[ ! -d ".git" ]]; then
  echo "Thu muc hien tai khong phai git repository."
  exit 1
fi

echo "Dang pull source moi nhat ..."
git pull --ff-only

echo "Dang dung stack hien tai ..."
docker compose -f "$COMPOSE_FILE" down --remove-orphans

echo "Dang xoa image backend cu neu co ..."
docker image rm -f "$BACKEND_IMAGE_NAME" 2>/dev/null || true

echo "Dang build lai backend ..."
docker compose -f "$COMPOSE_FILE" build --no-cache backend

echo "Dang chay lai stack ..."
docker compose -f "$COMPOSE_FILE" up -d

echo ""
echo "Trang thai container:"
docker compose -f "$COMPOSE_FILE" ps

echo ""
echo "Xem log neu can:"
echo "docker compose -f $COMPOSE_FILE logs -f backend"
echo "docker compose -f $COMPOSE_FILE logs -f caddy"
