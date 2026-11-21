"""Chat de la Ayuda: responde solo con texto que ya esta en la Ayuda, localmente y sin modelo."""
import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from nexus.ui import ayuda_chat as AC
from nexus.ui.tab_ayuda import FAQ, GLOSARIO

ROOT = Path(__file__).resolve().parent.parent
TEXTOS = {t for _, _, t in AC.entradas()}


def test_trae_toda_la_ayuda_como_fuente():
    from nexus.limitaciones import LIMITACIONES
    assert len(AC.entradas()) == len(GLOSARIO) + len(FAQ) + len(LIMITACIONES)


@pytest.mark.parametrize("pregunta,titulo", [
    ("¿Qué significa PROVISIONAL?", "PROVISIONAL"),
    ("qué es una discrepancia intercompañía", "Discrepancia intercompañía"),
    ("¿Por qué se bloquea un registro?", "Por qué se bloquea un registro"),
    ("qué es una tasa sospechosa", "Tasa sospechosa"),
    ("¿Se modifican mis archivos?", "¿Se modifican mis archivos?"),
    ("explícame el nivel de confianza", "Nivel de confianza"),
])
def test_responde_con_la_entrada_correcta(pregunta, titulo):
    r = AC.buscar(pregunta)
    assert r["encontrada"] and r["fuente"].endswith(titulo), r["fuente"]
    assert r["respuesta"] in TEXTOS                          # texto textual de la Ayuda: no inventa nada


@pytest.mark.parametrize("pregunta", ["", "   ", "¿cuál es la capital de Francia?", "asdf qwer", "dame la utilidad de 2030"])
def test_si_no_esta_en_la_ayuda_lo_dice_y_no_inventa(pregunta):
    r = AC.buscar(pregunta)
    assert not r["encontrada"] and r["respuesta"] == AC.NO_ENCONTRADO and r["fuente"] is None
    assert not re.search(r"\d{2,}[.,]\d", r["respuesta"])


def test_es_deterministico_y_no_usa_red_ni_modelo():
    assert AC.buscar("¿Qué es PROVISIONAL?") == AC.buscar("¿Qué es PROVISIONAL?")
    src = (ROOT / "nexus/ui/ayuda_chat.py").read_text(encoding="utf-8")
    assert not re.search(r"^\s*(from|import)\s+(requests|urllib|http|socket|anthropic|openai)", src, re.M)


def test_en_la_app_el_chat_responde_con_fuente_y_sin_falla():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120).run()
    at.radio(key="nav").set_value("Ayuda").run()
    assert not at.exception and len(at.chat_input) == 1
    assert any("sin modelo de lenguaje" in c.value for c in at.caption)
    at.chat_input[0].set_value("¿Qué significa PROVISIONAL?").run()
    assert not at.exception
    burbujas = [[x.value for x in m.markdown] for m in at.chat_message]
    assert burbujas[0] == ["¿Qué significa PROVISIONAL?"]
    assert burbujas[1][0].startswith(GLOSARIO[0][1]) or GLOSARIO[0][1] in burbujas[1][0]
    assert "Fuente: Ayuda → Glosario → PROVISIONAL" in burbujas[1][0]
    at.chat_input[0].set_value("capital de Francia").run()
    assert AC.NO_ENCONTRADO in [x.value for m in at.chat_message for x in m.markdown]
