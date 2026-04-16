#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

if [[ -f ".env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source ".env"
  set +a
fi

API_HOST="${API_HOST:-127.0.0.1}"
API_PORT="${API_PORT:-8000}"
NGROK_DOMAIN="${NGROK_DOMAIN:-film-stranger-algorithm.ngrok-free.dev}"
NGROK_AUTHTOKEN="${NGROK_AUTHTOKEN:-${NGROK_TOKEN_AUTH:-}}"
PUBLIC_BASE_URL="${PUBLIC_BASE_URL:-https://${NGROK_DOMAIN}}"

if [[ ! -x ".venv/bin/uvicorn" ]]; then
  echo "Khong tim thay .venv/bin/uvicorn. Hay tao venv va cai dependency truoc."
  exit 1
fi

if ! command -v ngrok >/dev/null 2>&1; then
  echo "Khong tim thay lenh 'ngrok'. Cai dat ngrok truoc khi chay script nay."
  echo "Docs: https://ngrok.com/docs/getting-started/"
  exit 1
fi

if [[ -n "$NGROK_AUTHTOKEN" ]]; then
  ngrok config add-authtoken "$NGROK_AUTHTOKEN" >/dev/null 2>&1 || true
fi

cleanup() {
  if [[ -n "${NGROK_PID:-}" ]] && kill -0 "$NGROK_PID" >/dev/null 2>&1; then
    kill "$NGROK_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "${API_PID:-}" ]] && kill -0 "$API_PID" >/dev/null 2>&1; then
    kill "$API_PID" >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT INT TERM

echo "Dang chay FastAPI tai http://${API_HOST}:${API_PORT} ..."
".venv/bin/uvicorn" app.api:app --host "$API_HOST" --port "$API_PORT" --reload &
API_PID=$!

for _ in {1..30}; do
  if curl -fsS "http://${API_HOST}:${API_PORT}/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if ! curl -fsS "http://${API_HOST}:${API_PORT}/health" >/dev/null 2>&1; then
  echo "API khong len duoc. Kiem tra log uvicorn."
  exit 1
fi

echo "Dang mo tunnel ngrok toi ${PUBLIC_BASE_URL} ..."
ngrok http "http://${API_HOST}:${API_PORT}" --url="$PUBLIC_BASE_URL" >/tmp/ptnk-ngrok.log 2>&1 &
NGROK_PID=$!

sleep 3

if ! kill -0 "$NGROK_PID" >/dev/null 2>&1; then
  echo "ngrok khong khoi dong duoc. Xem log:"
  cat /tmp/ptnk-ngrok.log
  exit 1
fi

echo ""
echo "API local:   http://${API_HOST}:${API_PORT}"
echo "API public:  ${PUBLIC_BASE_URL}"
echo "Swagger:     ${PUBLIC_BASE_URL}/docs"
echo ""
echo "Nhan Ctrl+C de dung ca API va ngrok."

wait "$NGROK_PID"
