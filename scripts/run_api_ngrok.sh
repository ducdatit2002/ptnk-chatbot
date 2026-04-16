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
  rm -f "$RUNTIME_URLS_PATH" "${NGROK_CONFIG_FILE:-}"
  if [[ -n "${NGROK_PID:-}" ]] && kill -0 "$NGROK_PID" >/dev/null 2>&1; then
    kill "$NGROK_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "${STREAMLIT_PID:-}" ]] && kill -0 "$STREAMLIT_PID" >/dev/null 2>&1; then
    kill "$STREAMLIT_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "${API_PID:-}" ]] && kill -0 "$API_PID" >/dev/null 2>&1; then
    kill "$API_PID" >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT INT TERM

echo "Dang chay Streamlit tai http://${STREAMLIT_HOST}:${STREAMLIT_PORT} ..."
".venv/bin/streamlit" run app/streamlit_app.py \
  --server.address "$STREAMLIT_HOST" \
  --server.port "$STREAMLIT_PORT" \
  --server.headless true >/tmp/ptnk-streamlit.log 2>&1 &
STREAMLIT_PID=$!

for _ in {1..30}; do
  if curl -fsS "http://${STREAMLIT_HOST}:${STREAMLIT_PORT}" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if ! curl -fsS "http://${STREAMLIT_HOST}:${STREAMLIT_PORT}" >/dev/null 2>&1; then
  echo "Streamlit khong len duoc. Kiem tra log /tmp/ptnk-streamlit.log"
  exit 1
fi

NGROK_CONFIG_FILE="$NGROK_WORKDIR/ngrok-agent.yml"

cat >"$NGROK_CONFIG_FILE" <<EOF
version: 3
agent:
  authtoken: ${NGROK_AUTHTOKEN}
  web_addr: 127.0.0.1:4040
  log: ${NGROK_WORKDIR}/agent.log
  console_ui: false
endpoints:
  - name: api
    url: https://${NGROK_DOMAIN}
    upstream:
      url: http://${API_HOST}:${API_PORT}
EOF

if [[ -n "$STREAMLIT_NGROK_URL" ]]; then
  cat >>"$NGROK_CONFIG_FILE" <<EOF
  - name: streamlit
    url: ${STREAMLIT_NGROK_URL}
    upstream:
      url: http://${STREAMLIT_HOST}:${STREAMLIT_PORT}
EOF
else
  cat >>"$NGROK_CONFIG_FILE" <<EOF
  - name: streamlit
    upstream:
      url: http://${STREAMLIT_HOST}:${STREAMLIT_PORT}
EOF
fi

echo "Dang mo cac tunnel ngrok ..."
ngrok start --all --config "$NGROK_CONFIG_FILE" >"${NGROK_WORKDIR}/ngrok.log" 2>&1 &
NGROK_PID=$!

for _ in {1..30}; do
  if curl -fsS "http://127.0.0.1:4040/api/tunnels" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if ! curl -fsS "http://127.0.0.1:4040/api/tunnels" >/dev/null 2>&1; then
  echo "ngrok khong khoi dong duoc. Xem log:"
  cat "${NGROK_WORKDIR}/ngrok.log"
  exit 1
fi

TUNNEL_JSON="$(curl -fsS "http://127.0.0.1:4040/api/tunnels")"
URLS_JSON="$(python3 - <<'PY' "$TUNNEL_JSON"
import json
import sys

payload = json.loads(sys.argv[1])
result = {}
for item in payload.get("tunnels", []):
    name = str(item.get("name", "")).strip()
    public_url = str(item.get("public_url", "")).strip()
    if name == "api" and public_url:
        result["api_public_url"] = public_url
    if name == "streamlit" and public_url:
        result["streamlit_public_url"] = public_url
print(json.dumps(result, ensure_ascii=False))
PY
)"

API_PUBLIC_URL="$(python3 - <<'PY' "$URLS_JSON"
import json
import sys
payload = json.loads(sys.argv[1])
print(payload.get("api_public_url", ""))
PY
)"

STREAMLIT_PUBLIC_URL_RUNTIME="$(python3 - <<'PY' "$URLS_JSON"
import json
import sys
payload = json.loads(sys.argv[1])
print(payload.get("streamlit_public_url", ""))
PY
)"

if [[ -z "$API_PUBLIC_URL" ]]; then
  echo "Khong lay duoc public URL cua API tu ngrok."
  cat "${NGROK_WORKDIR}/ngrok.log"
  exit 1
fi

cat >"$RUNTIME_URLS_PATH" <<EOF
{
  "api_public_url": "${API_PUBLIC_URL}",
  "streamlit_public_url": "${STREAMLIT_PUBLIC_URL_RUNTIME}"
}
EOF

export PUBLIC_BASE_URL="$API_PUBLIC_URL"

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

echo ""
echo "API local:        http://${API_HOST}:${API_PORT}"
echo "API public:       ${API_PUBLIC_URL}"
echo "Swagger public:   ${API_PUBLIC_URL}/docs"
echo "Streamlit local:  http://${STREAMLIT_HOST}:${STREAMLIT_PORT}"
if [[ -n "$STREAMLIT_PUBLIC_URL_RUNTIME" ]]; then
  echo "Streamlit public: ${STREAMLIT_PUBLIC_URL_RUNTIME}"
fi
echo "Redirect route:   ${API_PUBLIC_URL}/streamlit"
echo ""
echo "Nhan Ctrl+C de dung API, Streamlit va ngrok."

wait "$NGROK_PID"
