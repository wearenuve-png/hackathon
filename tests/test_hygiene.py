"""Credibilidad del repositorio: el prototipo anterior no entra al flujo ni los archivos fuente cambian."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_el_prototipo_validador_no_se_importa_desde_el_flujo():
    files = list((ROOT / "nexus").rglob("*.py")) + [ROOT / "app.py"] + list((ROOT / "scripts").glob("*.py"))
    for f in files:
        txt = f.read_text(encoding="utf-8")
        assert not re.search(r"^\s*(from|import)\s+validador\b", txt, re.M), f"{f} importa el prototipo"


def test_prototipo_esta_documentado_como_referencia():
    assert "SOLO REFERENCIA" in (ROOT / "validador" / "README.md").read_text(encoding="utf-8")
