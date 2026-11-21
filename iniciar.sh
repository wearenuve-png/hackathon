#!/usr/bin/env bash
# FinaCore: prepara el entorno la primera vez y abre la app. Mac y Linux.
#   ./iniciar.sh              -> prepara (si hace falta) y abre la app en http://localhost:8501
#   ./iniciar.sh --preparar   -> solo prepara el entorno
#   PUERTO=8502 ./iniciar.sh  -> usa otro puerto
set -e
cd "$(dirname "$0")"
PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then echo "Necesitas Python 3.9 o superior (https://www.python.org/downloads/)."; exit 1; fi
if [ ! -x ".venv/bin/streamlit" ]; then
  echo "Primera vez: instalando dependencias (necesita internet, tarda un par de minutos)..."
  "$PY" -m venv .venv
  .venv/bin/pip install --quiet --upgrade pip
  .venv/bin/pip install --quiet -r requirements.txt
fi
[ "$1" = "--preparar" ] && { echo "Entorno listo."; exit 0; }
exec .venv/bin/streamlit run app.py --server.port "${PUERTO:-8501}"
