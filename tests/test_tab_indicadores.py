"""La pestana muestra formula, entradas y resultado (prueba real con streamlit AppTest)."""
from decimal import Decimal
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from conftest import DATA, KEY

ROOT = Path(__file__).resolve().parent.parent
CODE = """
import sys
sys.path.insert(0, {root!r})
import streamlit as st
from nexus.pipeline import run
from nexus.ui.tab_indicadores import render

@st.cache_resource
def _run():
    return run({data!r})

render(_run(), {period!r})
"""


def app(period="2026-10"):
    at = AppTest.from_string(CODE.format(root=str(ROOT), data=str(DATA), period=period), default_timeout=90).run()
    assert not at.exception, at.exception
    return at


def frames(at):
    return [d.value for d in at.dataframe]


def test_muestra_formula_entradas_y_resultado_de_octubre():
    at = app()
    forms = next(f for f in frames(at) if "Formula" in f.columns)
    assert list(forms["Indicador"]) == ["NOPAT", "ROIC", "ROCE", "EVA"]
    assert "NOPAT / capital invertido" in forms[forms["Indicador"] == "ROIC"].iloc[0]["Formula"]
    k = KEY["consolidado_esperado_usd"]["2026-10"]
    nopat = Decimal(k["resumen"]["ebit"]) * Decimal("0.75")
    ci = Decimal(k["por_cuenta"]["2500"]) + Decimal(k["resumen"]["patrimonio"]) - Decimal(k["por_cuenta"]["1000"])
    assert forms[forms["Indicador"] == "ROIC"].iloc[0]["Resultado"] == f"{nopat / ci:.2%}"
    assert f"{ci:,.2f}" in forms[forms["Indicador"] == "ROIC"].iloc[0]["Con las entradas"]
    entradas = next(f for f in frames(at) if "Origen" in f.columns)
    origen = dict(zip(entradas["Entrada"], entradas["Origen"]))
    assert origen["WACC (anual)"] == "SUPUESTO" and origen["EBIT del periodo"] == "CONSOLIDADO"


def test_etiqueta_supuesto_y_provisional_visibles():
    at = app()
    assert any("SUPUESTO" in w.value for w in at.warning)
    assert any("PROVISIONAL" in e.value for e in at.error)
    assert [m.label for m in at.metric] == ["ROIC (mensual)", "ROCE (mensual)", "EVA (mensual, USD)"]
    assert all(not m.delta for m in at.metric)                                    # nada anualizado en la vista principal
    pie = [c.value for c in at.caption if "Anualizados" in c.value]
    assert len(pie) == 1 and "no son representativos por ser datos sinteticos" in pie[0]


@pytest.mark.parametrize("periodo", list(KEY["consolidado_esperado_usd"]))
def test_los_tres_periodos_se_renderizan(periodo):
    at = app(periodo)
    assert not at.exception and at.metric[0].value.endswith("%")


def test_un_supuesto_invalido_se_ve_como_error():
    at = app()
    at.number_input(key="ind_wacc_2026-10").set_value(800.0).run()          # 800% de WACC
    assert not at.exception
    assert any("IND-03" in e.value for e in at.error)
    assert at.metric[2].value == "n/c"                                       # EVA no se calcula
