#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
URL="http://${HOST}:${PORT}/"
VENV_DIR="${VENV_DIR:-.venv}"
PYTHON_CMD="${VENV_DIR}/bin/python"
BOOTSTRAP_PY=""

if command -v python3 >/dev/null 2>&1; then
    BOOTSTRAP_PY="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
    BOOTSTRAP_PY="$(command -v python)"
else
    echo "Python nu a fost gasit. Instaleaza Python 3 si ruleaza din nou scriptul."
    exit 1
fi

if [ ! -x "${PYTHON_CMD}" ]; then
    echo "Creez mediul virtual in ${VENV_DIR}..."
    "${BOOTSTRAP_PY}" -m venv "${VENV_DIR}"
    "${PYTHON_CMD}" -m pip install -r requirements.txt
fi

echo "Pornire Logistica Vietii Web la ${URL}"

if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "${URL}" >/dev/null 2>&1 &
elif command -v open >/dev/null 2>&1; then
    open "${URL}" >/dev/null 2>&1 &
fi

exec "${PYTHON_CMD}" webapp.py --host "${HOST}" --port "${PORT}"
