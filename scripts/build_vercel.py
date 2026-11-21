"""Genera vercel/: FinaCore como sitio ESTATICO que corre dentro del navegador (stlite = Streamlit sobre WebAssembly).

Vercel no puede ejecutar un servidor de Streamlit; si puede servir archivos estaticos. El navegador baja Python
(Pyodide) y corre app.py y el motor localmente: los archivos del usuario NUNCA salen de su navegador.

    python scripts/build_vercel.py          # reescribe vercel/ (index.html, bundle.zip, app.py.txt, vercel.json)

En Vercel: Settings > General > Root Directory = vercel. Sin comando de compilacion.
"""
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "vercel"
STLITE = "0.85.1"
INCLUIR = [("nexus", "**/*.py"), ("asistente", "*.py"), ("config", "*.json"),
           ("data/demo", "*"), ("data/demo_ampliado", "*")]
REQUISITOS = ["pandas", "openpyxl", "altair"]
FECHA = (2026, 11, 21, 12, 0, 0)

HTML = """<!doctype html>
<html lang="es">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>FinaCore | Consolidación</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@stlite/browser@__V__/build/stlite.css" />
<style>body{margin:0;background:#181716}</style>
</head>
<body>
<div id="root"></div>
<script type="module">
import { mount } from "https://cdn.jsdelivr.net/npm/@stlite/browser@__V__/build/stlite.js";
mount({
  entrypoint: "app.py",
  files: { "app.py": { url: "./app.py.txt" } },
  archives: [{ url: "./bundle.zip", format: "zip" }],
  requirements: __REQ__,
  streamlitConfig: { "theme.base": "dark", "client.toolbarMode": "minimal" }
}, document.getElementById("root"));
</script>
</body>
</html>
"""
VERCEL_JSON = {"framework": None, "buildCommand": None, "installCommand": None, "outputDirectory": "."}


# La version de Streamlit dentro de stlite puede ser mas vieja que la 1.50 de requirements.txt: este encabezado (solo
# en la copia web de app.py) descarta o traduce los argumentos nuevos que esa version no conoce.
COMPAT = '''import functools as _ft
import inspect as _insp

import streamlit as _stc
from streamlit.delta_generator import DeltaGenerator as _DG

_NOMBRES = ["radio", "dataframe", "button", "columns", "container", "error", "success", "info", "warning", "markdown",
            "caption", "selectbox", "text_input", "text_area", "file_uploader", "download_button", "altair_chart",
            "expander", "metric", "slider", "chat_input", "chat_message", "toggle", "checkbox", "multiselect",
            "number_input", "write", "table", "progress", "form_submit_button"]


def _envolver(orig, ps):
    @_ft.wraps(orig)
    def f(self, *a, **k):
        if isinstance(k.get("width"), str):                 # width="stretch" (Streamlit nuevo) -> use_container_width
            if k["width"] == "stretch" and "use_container_width" in ps:
                k["use_container_width"] = True
            k.pop("width")
        if k.get("type") == "tertiary" and "type" in ps:
            k["type"] = "secondary"
        for clave in [c for c in k if c not in ps]:
            k.pop(clave)
        return orig(self, *a, **k)
    return f


for _n in _NOMBRES:
    _o = getattr(_DG, _n, None)
    if _o is None:
        continue
    try:
        _ps = _insp.signature(_o).parameters
    except (TypeError, ValueError):
        continue
    if any(p.kind == p.VAR_KEYWORD for p in _ps.values()):
        continue
    setattr(_DG, _n, _envolver(_o, _ps))
    if hasattr(_stc, _n):
        setattr(_stc, _n, getattr(_stc._main, _n))
'''


def archivos():
    for carpeta, patron in INCLUIR:
        for f in sorted((ROOT / carpeta).glob(patron)):
            if f.is_file() and "__pycache__" not in f.parts and f.suffix != ".pyc":
                yield f.relative_to(ROOT).as_posix(), f


def main(out: Path = OUT) -> None:
    out.mkdir(exist_ok=True)
    with zipfile.ZipFile(out / "bundle.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for nombre, f in archivos():
            zi = zipfile.ZipInfo(nombre, FECHA)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o644 << 16
            z.writestr(zi, f.read_bytes())
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    ancla = "import sys\n"                       # el encabezado va antes de usar Streamlit, tras el docstring
    i = app.index(ancla)
    (out / "app.py.txt").write_text(app[:i] + COMPAT + "\n" + app[i:], encoding="utf-8")
    (out / "index.html").write_text(HTML.replace("__V__", STLITE).replace("__REQ__", json.dumps(REQUISITOS)),
                                    encoding="utf-8")
    (out / "vercel.json").write_text(json.dumps(VERCEL_JSON, indent=2) + "\n", encoding="utf-8")
    print(f"vercel/ listo: {sum(1 for _ in archivos())} archivos en bundle.zip")


if __name__ == "__main__":
    main()
