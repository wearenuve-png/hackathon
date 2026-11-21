"""Version web estatica (stlite) para Vercel: se genera con scripts/build_vercel.py y lo comprometido esta al dia."""
import ast
import importlib.util
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("build_vercel", ROOT / "scripts" / "build_vercel.py")
BV = importlib.util.module_from_spec(spec)
spec.loader.exec_module(BV)


def test_lo_comprometido_en_vercel_es_lo_que_genera_el_script(tmp_path):
    BV.main(tmp_path)
    for f in ("index.html", "app.py.txt", "vercel.json"):
        assert (tmp_path / f).read_bytes() == (ROOT / "vercel" / f).read_bytes(), f"vercel/{f} esta desactualizado: correr scripts/build_vercel.py"
    assert (tmp_path / "bundle.zip").read_bytes() == (ROOT / "vercel" / "bundle.zip").read_bytes()


def test_el_paquete_trae_el_motor_los_datos_de_prueba_y_nada_de_pruebas():
    nombres = zipfile.ZipFile(ROOT / "vercel" / "bundle.zip").namelist()
    for esperado in ("nexus/pipeline.py", "nexus/ui/carga_auto.py", "asistente/tab.py", "config/asistente.json",
                     "data/demo/empresas.csv", "data/demo_ampliado/empresas.csv"):
        assert esperado in nombres, esperado
    assert not [n for n in nombres if n.startswith(("tests/", "scripts/", "docs/", ".venv")) or "__pycache__" in n]
    assert not [n for n in nombres if "ANSWER_KEY" in n or n.startswith(("data/synthetic", "data/demo_errores"))]


def test_la_copia_web_de_app_py_es_python_valido_y_trae_el_encabezado_de_compatibilidad():
    txt = (ROOT / "vercel" / "app.py.txt").read_text(encoding="utf-8")
    ast.parse(txt)
    assert "_envolver" in txt and txt.count("st.set_page_config") == 1


def test_la_configuracion_para_vercel_es_estatica_y_sin_python():
    for ruta in (ROOT / "vercel.json", ROOT / "vercel" / "vercel.json"):
        cfg = json.loads(ruta.read_text())
        assert cfg["framework"] is None and cfg["buildCommand"] is None
    assert not list((ROOT / "vercel").glob("*.py")) and not (ROOT / "vercel" / "requirements.txt").exists()
    html = (ROOT / "vercel" / "index.html").read_text(encoding="utf-8")
    assert "@stlite/browser@" in html and 'entrypoint: "app.py"' in html and "bundle.zip" in html
