#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-.venv}"
API_HOST="${API_HOST:-127.0.0.1}"
API_PORT="${API_PORT:-8000}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Khong tim thay $PYTHON_BIN. Hay cai Python 3.11 hoac 3.12 truoc."
  exit 1
fi

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  echo "Dang tao virtualenv tai $VENV_DIR ..."
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

if [[ ! -x "$VENV_DIR/bin/pip" ]]; then
  echo "Khong tim thay pip trong $VENV_DIR."
  exit 1
fi

echo "Dang cai dependency ..."
"$VENV_DIR/bin/pip" install -r requirements.txt

echo "Dang chay API tai http://${API_HOST}:${API_PORT} ..."
exec "$VENV_DIR/bin/uvicorn" app.api:app --host "$API_HOST" --port "$API_PORT" --reload
