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
STREAMLIT_HOST="${STREAMLIT_HOST:-127.0.0.1}"
STREAMLIT_PORT="${STREAMLIT_PORT:-8501}"
NGROK_DOMAIN="${NGROK_DOMAIN:-film-stranger-algorithm.ngrok-free.dev}"
NGROK_AUTHTOKEN="${NGROK_AUTHTOKEN:-${NGROK_TOKEN_AUTH:-}}"
RUNTIME_URLS_PATH="${RUNTIME_URLS_PATH:-$PROJECT_ROOT/storage/runtime_urls.json}"
NGROK_WORKDIR="${NGROK_WORKDIR:-$PROJECT_ROOT/storage/ngrok}"
STREAMLIT_NGROK_URL="${STREAMLIT_NGROK_URL:-${STREAMLIT_PUBLIC_URL:-}}"
API_NGROK_WEB_ADDR="${API_NGROK_WEB_ADDR:-127.0.0.1:4040}"
STREAMLIT_NGROK_WEB_ADDR="${STREAMLIT_NGROK_WEB_ADDR:-127.0.0.1:4041}"

mkdir -p "$(dirname "$RUNTIME_URLS_PATH")"
mkdir -p "$NGROK_WORKDIR"

if [[ ! -x ".venv/bin/uvicorn" ]]; then
  echo "Khong tim thay .venv/bin/uvicorn. Hay tao venv va cai dependency truoc."
  exit 1
fi

if [[ ! -x ".venv/bin/streamlit" ]]; then
  echo "Khong tim thay .venv/bin/streamlit. Hay cai dependency truoc."
  exit 1
fi

if ! command -v ngrok >/dev/null 2>&1; then
  echo "Khong tim thay lenh 'ngrok'. Cai dat ngrok truoc khi chay script nay."
  echo "Docs: https://ngrok.com/docs/getting-started/"
  exit 1
fi

if [[ -z "$NGROK_AUTHTOKEN" ]]; then
  echo "Thieu NGROK_AUTHTOKEN / NGROK_TOKEN_AUTH trong .env"
  exit 1
fi

cleanup() {
  rm -f "$RUNTIME_URLS_PATH" "${API_NGROK_CONFIG:-}" "${STREAMLIT_NGROK_CONFIG:-}"
  if [[ -n "${API_NGROK_PID:-}" ]] && kill -0 "$API_NGROK_PID" >/dev/null 2>&1; then
    kill "$API_NGROK_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "${STREAMLIT_NGROK_PID:-}" ]] && kill -0 "$STREAMLIT_NGROK_PID" >/dev/null 2>&1; then
    kill "$STREAMLIT_NGROK_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "${STREAMLIT_PID:-}" ]] && kill -0 "$STREAMLIT_PID" >/dev/null 2>&1; then
    kill "$STREAMLIT_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "${API_PID:-}" ]] && kill -0 "$API_PID" >/dev/null 2>&1; then
    kill "$API_PID" >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT INT TERM

wait_for_http() {
  local url="$1"
  local attempts="${2:-30}"
  for _ in $(seq 1 "$attempts"); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}

extract_first_https_url() {
  local api_url="$1"
  python3 - <<'PY' "$api_url"
import json
import sys
from urllib.request import urlopen

api_url = sys.argv[1]
with urlopen(api_url) as response:
    payload = json.load(response)

for item in payload.get("tunnels", []):
    public_url = str(item.get("public_url", "")).strip()
    if public_url.startswith("https://"):
        print(public_url)
        break
PY
}

echo "Dang chay FastAPI tai http://${API_HOST}:${API_PORT} ..."
".venv/bin/uvicorn" app.api:app --host "$API_HOST" --port "$API_PORT" --reload >/tmp/ptnk-api.log 2>&1 &
API_PID=$!

if ! wait_for_http "http://${API_HOST}:${API_PORT}/health" 30; then
  echo "API khong len duoc. Kiem tra log /tmp/ptnk-api.log"
  exit 1
fi

echo "Dang chay Streamlit tai http://${STREAMLIT_HOST}:${STREAMLIT_PORT} ..."
".venv/bin/streamlit" run app/streamlit_app.py \
  --server.address "$STREAMLIT_HOST" \
  --server.port "$STREAMLIT_PORT" \
  --server.headless true >/tmp/ptnk-streamlit.log 2>&1 &
STREAMLIT_PID=$!

if ! wait_for_http "http://${STREAMLIT_HOST}:${STREAMLIT_PORT}" 30; then
  echo "Streamlit khong len duoc. Kiem tra log /tmp/ptnk-streamlit.log"
  exit 1
fi

API_NGROK_CONFIG="$NGROK_WORKDIR/ngrok-api.yml"
STREAMLIT_NGROK_CONFIG="$NGROK_WORKDIR/ngrok-streamlit.yml"

cat >"$API_NGROK_CONFIG" <<EOF
version: 3
agent:
  authtoken: ${NGROK_AUTHTOKEN}
  web_addr: ${API_NGROK_WEB_ADDR}
  console_ui: false
EOF

cat >"$STREAMLIT_NGROK_CONFIG" <<EOF
version: 3
agent:
  authtoken: ${NGROK_AUTHTOKEN}
  web_addr: ${STREAMLIT_NGROK_WEB_ADDR}
  console_ui: false
EOF

echo "Dang mo cac tunnel ngrok ..."
ngrok http "http://${API_HOST}:${API_PORT}" \
  --url "https://${NGROK_DOMAIN}" \
  --name api \
  --config "$API_NGROK_CONFIG" \
  --log "${NGROK_WORKDIR}/api-ngrok.log" \
  --log-format logfmt \
  --log-level info >/dev/null 2>&1 &
API_NGROK_PID=$!

streamlit_ngrok_cmd=(
  ngrok http "http://${STREAMLIT_HOST}:${STREAMLIT_PORT}"
  --name streamlit
  --config "$STREAMLIT_NGROK_CONFIG"
  --log "${NGROK_WORKDIR}/streamlit-ngrok.log"
  --log-format logfmt
  --log-level info
)

if [[ -n "$STREAMLIT_NGROK_URL" ]]; then
  streamlit_ngrok_cmd+=(--url "$STREAMLIT_NGROK_URL")
fi

"${streamlit_ngrok_cmd[@]}" >/dev/null 2>&1 &
STREAMLIT_NGROK_PID=$!

if ! wait_for_http "http://${API_NGROK_WEB_ADDR}/api/tunnels" 30; then
  echo "ngrok API tunnel khong khoi dong duoc. Xem log:"
  cat "${NGROK_WORKDIR}/api-ngrok.log"
  exit 1
fi

if ! wait_for_http "http://${STREAMLIT_NGROK_WEB_ADDR}/api/tunnels" 30; then
  echo "ngrok Streamlit tunnel khong khoi dong duoc. Xem log:"
  cat "${NGROK_WORKDIR}/streamlit-ngrok.log"
  exit 1
fi

API_PUBLIC_URL="$(extract_first_https_url "http://${API_NGROK_WEB_ADDR}/api/tunnels")"
STREAMLIT_PUBLIC_URL_RUNTIME="$(extract_first_https_url "http://${STREAMLIT_NGROK_WEB_ADDR}/api/tunnels")"

if [[ -z "$API_PUBLIC_URL" ]]; then
  echo "Khong lay duoc public URL cua API tu ngrok."
  curl -fsS "http://${API_NGROK_WEB_ADDR}/api/tunnels" || true
  cat "${NGROK_WORKDIR}/api-ngrok.log"
  exit 1
fi

if [[ -z "$STREAMLIT_PUBLIC_URL_RUNTIME" ]]; then
  echo "Khong lay duoc public URL cua Streamlit tu ngrok."
  curl -fsS "http://${STREAMLIT_NGROK_WEB_ADDR}/api/tunnels" || true
  cat "${NGROK_WORKDIR}/streamlit-ngrok.log"
  exit 1
fi

if [[ "$API_PUBLIC_URL" == "$STREAMLIT_PUBLIC_URL_RUNTIME" ]]; then
  echo "ngrok dang tra ve cung mot public URL cho API va Streamlit. Dung script de tranh route sai."
  echo "API tunnel:"
  curl -fsS "http://${API_NGROK_WEB_ADDR}/api/tunnels" || true
  echo ""
  echo "Streamlit tunnel:"
  curl -fsS "http://${STREAMLIT_NGROK_WEB_ADDR}/api/tunnels" || true
  exit 1
fi

cat >"$RUNTIME_URLS_PATH" <<EOF
{
  "api_public_url": "${API_PUBLIC_URL}",
  "streamlit_public_url": "${STREAMLIT_PUBLIC_URL_RUNTIME}"
}
EOF

echo ""
echo "API local:        http://${API_HOST}:${API_PORT}"
echo "API public:       ${API_PUBLIC_URL}"
echo "Swagger public:   ${API_PUBLIC_URL}/docs"
echo "Streamlit local:  http://${STREAMLIT_HOST}:${STREAMLIT_PORT}"
echo "Streamlit public: ${STREAMLIT_PUBLIC_URL_RUNTIME}"
echo "Redirect route:   ${API_PUBLIC_URL}/streamlit"
echo ""
echo "Nhan Ctrl+C de dung API, Streamlit va ngrok."

wait "$API_PID"
