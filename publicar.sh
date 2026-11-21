#!/usr/bin/env bash
# FinaCore en internet con un tunel de Cloudflare (enlace https://....trycloudflare.com). Mac y Linux.
#   ./publicar.sh        -> arranca la app en MODO PUBLICO y abre el tunel; Ctrl+C lo cierra todo.
# Requiere cloudflared (mac: brew install cloudflared). El enlace deja de funcionar al cerrar este script.
set -e
cd "$(dirname "$0")"
command -v cloudflared >/dev/null || { echo "Falta cloudflared: brew install cloudflared"; exit 1; }
./iniciar.sh --preparar
export FINACORE_PUBLICO=1
.venv/bin/streamlit run app.py --server.port 8501 --server.headless true >/tmp/finacore_app.log 2>&1 &
APP=$!
trap 'kill $APP 2>/dev/null' EXIT
sleep 4
echo "App local lista. Abriendo el tunel; busca la linea https://....trycloudflare.com"
cloudflared tunnel --url http://localhost:8501
