"""Explicador de variaciones: las causas suman exacto el total; las frases coinciden con la tabla."""
import re
from decimal import Decimal

import pytest
from streamlit.testing.v1 import AppTest

from conftest import DATA, KEY, ROOT
from nexus import variance as V
from nexus.pipeline import run
from nexus.schemas import BLOCK

D = Decimal
PERIODOS = sorted(KEY["consolidado_esperado_usd"])
PARES = list(zip(PERIODOS, PERIODOS[1:]))


@pytest.fixture(scope="module")
def res():
    return run(DATA, ic_tolerance_usd=KEY["tolerancia_intercompania_usd"], profiles_dir=ROOT / "profiles")


@pytest.fixture(scope="module")
def reports(res):
    return {(a, b): V.compare(V.view(res, a), V.view(res, b)) for a, b in PARES}


# ---------------------------------------------------------------- a mano
def test_ejemplo_a_mano_mxn():
    """1,000,000 MXN x 0.05 = 50,000 -> 1,100,000 MXN x 0.0525 = 57,750: total +7,750 = operacion +5,000 + TC +2,750."""
    op, fx = V.decompose(D("1000000"), D("1100000"), D("0.05"), D("0.0525"))
    assert (op, fx) == (D("5000"), D("2750")) and op + fx == D("57750") - D("50000") == D("7750")


def test_ejemplo_a_mano_de_punta_a_punta(tmp_path):
    """El mismo caso pasando por el motor completo con datos minimos."""
    from test_matriz_errores import RATES, make, row
    rates = dict(RATES)
    rates[("MXN", "2026-11")] = "0.0525"
    res, _ = make(tmp_path, [row("2026-10", "Ventas", 1000000, "MXN"), row("2026-11", "Ventas", 1100000, "MXN")],
                  rates=rates, periods=("2026-10", "2026-11"), a_cur="MXN")
    rep = V.compare(V.view(res, "2026-10"), V.view(res, "2026-11"))
    v = rep.by_account["4000"]
    assert (v.prev, v.cur, v.total) == (D("50000"), D("57750"), D("7750"))
    assert v.causes[V.OP] == D("5000") and v.causes[V.FX] == D("2750")
    assert all(v.causes[k] == 0 for k in (V.ELIM, V.AJ, V.MES, V.SIN))
    assert rep.total.total == D("7750") and not rep.by_account["4000"].material           # 7,750 < 10,000
    assert "+5,000.00" in v.phrase and "+2,750.00" in v.phrase


# ---------------------------------------------------------------- todos los periodos de la clave
@pytest.mark.parametrize("par", PARES)
def test_causas_mas_sin_explicar_igual_al_total_en_todos_los_niveles(reports, par):
    rep = reports[par]
    todas = list(rep.by_account.values()) + list(rep.by_company.values()) + list(rep.cells.values()) + [rep.total]
    for v in todas:
        assert v.causes_sum == v.total, v.label                                            # suma EXACTA, en Decimal
        assert v.cur - v.prev == v.total


@pytest.mark.parametrize("par", PARES)
def test_variacion_por_cuenta_igual_a_la_clave(reports, par):
    a, b = par
    rep = reports[par]
    ka, kb = KEY["consolidado_esperado_usd"][a]["por_cuenta"], KEY["consolidado_esperado_usd"][b]["por_cuenta"]
    for code, v in rep.by_account.items():
        assert abs(v.total - (D(kb[code]) - D(ka[code]))) <= D("0.011"), code
        assert abs(v.prev - D(ka[code])) <= D("0.006") and abs(v.cur - D(kb[code])) <= D("0.006")
    ra, rb = KEY["consolidado_esperado_usd"][a]["resumen"], KEY["consolidado_esperado_usd"][b]["resumen"]
    assert abs(rep.total.total - (D(rb["utilidad_neta"]) - D(ra["utilidad_neta"]))) <= D("0.011")
    assert sum((v.total for v in rep.by_company.values()), D(0)) == rep.total.total       # empresas suman el total


@pytest.mark.parametrize("par", PARES)
def test_sin_explicar_solo_aparece_con_una_razon_a_la_vista(reports, par):
    """Nada se reparte a ciegas: cada celda con 'sin explicar' trae una nota que dice por que."""
    for k, v in reports[par].cells.items():
        if v.causes[V.SIN] != 0:
            assert v.notes, f"{k} tiene sin explicar sin nota"
            assert any(("bloqueado" in n or "cambio" in n or "tasa" in n.lower()) for n in v.notes)


def test_oct_nov_explica_el_mes_faltante_y_el_registro_bloqueado(reports):
    rep = reports[("2026-10", "2026-11")]
    assert rep.total.causes[V.MES] != 0 and rep.provisional                  # EMP006 no entrego noviembre
    cell = rep.cells[("EMP002", "6000")]                                     # planilla con moneda "Q"
    assert cell.causes[V.SIN] != 0 and any("'Q'" in n for n in cell.notes)
    assert "PROVISIONAL" in rep.total.tags


def test_nov_dic_marca_el_cambio_de_moneda_sin_adivinar(reports):
    cell = reports[("2026-11", "2026-12")].cells[("EMP002", "6100")]         # alquiler GTQ -> USD (error 7)
    assert cell.causes[V.SIN] == cell.total != 0 and any("moneda" in n for n in cell.notes)
    assert cell.causes[V.OP] == cell.causes[V.FX] == 0


# ---------------------------------------------------------------- frases = tabla
@pytest.mark.parametrize("par", PARES)
def test_las_cifras_de_las_frases_coinciden_con_la_tabla(reports, par):
    rep = reports[par]
    num = re.compile(r"[+-]?\d[\d,]*\.\d{2}")
    for v in list(rep.by_account.values()) + list(rep.by_company.values()) + [rep.total]:
        permitidos = set()
        for x in [v.prev, v.cur, v.total, abs(v.total)] + list(v.causes.values()):
            permitidos |= {V.fmt(x), V.sfmt(x), V.fmt(abs(x))}
        for n in num.findall(v.phrase):
            assert n in permitidos, f"{v.label}: la frase dice {n}, que no esta en la tabla"
        for k, x in v.causes.items():                                         # y cada causa distinta de 0 se nombra
            if x != 0:
                assert f"{V.CAUSE_NAMES[k].lower()} {V.sfmt(x)} USD" in v.phrase


def test_la_traza_llega_a_archivo_hoja_y_fila(reports):
    v = reports[("2026-10", "2026-11")].by_account["4000"]
    assert v.trace and all(t.file and t.row for t in v.trace)
    assert any(t.sheet for t in v.trace) and any("IC-ELIM-01" in t.rule for t in v.trace)
    assert any(t.rate is not None for t in v.trace)


# ---------------------------------------------------------------- umbral configurable y validado
def test_umbral_por_defecto_viene_de_config_y_es_supuesto():
    p = V.load_params()
    assert (p.min_pct, p.min_abs_usd) == (D("0.05"), D("10000"))
    import json
    assert "SUPUESTO" in json.loads(V.DEFAULT_CONFIG.read_text(encoding="utf-8"))["_nota"]


def test_materialidad_exige_ambos_umbrales(reports):
    rep = reports[("2026-10", "2026-11")]
    for v in rep.by_account.values():
        assert v.material == (abs(v.total) >= D("10000") and (v.pct is None or abs(v.pct) >= D("0.05")))
    assert any(not v.material for v in rep.by_account.values()) and any(v.material for v in rep.by_account.values())


@pytest.mark.parametrize("params,rule", [(V.VarianceParams(D("5"), D("10000")), "VAR-01"),
                                         (V.VarianceParams(D("0.05"), D("-1")), "VAR-02")])
def test_umbral_invalido_bloquea_el_explicador(res, params, rule):
    rep = V.compare(V.view(res, "2026-10"), V.view(res, "2026-11"), params=params)
    assert rep.blocked and rule in {f.rule_id for f in rep.findings if f.severity == BLOCK}
    assert rep.total is None and not rep.by_account


def test_otro_umbral_cambia_lo_material(res):
    todo = V.compare(V.view(res, "2026-10"), V.view(res, "2026-11"), params=V.VarianceParams(D("0"), D("0")))
    nada = V.compare(V.view(res, "2026-10"), V.view(res, "2026-11"), params=V.VarianceParams(D("0.9"), D("10000000")))
    assert sum(v.material for v in todo.by_account.values()) > 0 == sum(v.material for v in nada.by_account.values())


def test_no_modifica_el_consolidado(res):
    antes = {p: dict(pr.summary) for p, pr in res.periods.items()}
    V.compare(V.view(res, "2026-10"), V.view(res, "2026-12"))
    assert {p: pr.summary for p, pr in res.periods.items()} == antes


# ---------------------------------------------------------------- interfaz
CODE = """
import sys
sys.path.insert(0, {root!r})
import streamlit as st
from nexus.pipeline import run
from nexus import variance as V
from nexus.ui.tab_variaciones import render

@st.cache_resource
def _run():
    return run({data!r}, profiles_dir={prof!r})

r = _run()
render(V.view(r, {cur!r}), {prev})
"""


def app(cur="2026-11", prev="2026-10"):
    prev_code = f"V.view(r, {prev!r})" if prev else "None"
    at = AppTest.from_string(CODE.format(root=str(ROOT), data=str(DATA), prof=str(ROOT / "profiles"), cur=cur,
                                         prev=prev_code), default_timeout=90).run()
    assert not at.exception, at.exception
    return at


def test_la_pestana_muestra_frase_causas_y_trazabilidad():
    at = app()
    texto = " ".join(m.value for m in at.markdown)
    assert "La utilidad neta consolidada baja 80,315.00 USD" in texto
    tablas = [d.value for d in at.dataframe]
    causas = next(t for t in tablas if "Causa" in t.columns)
    assert causas.iloc[-1]["Causa"].startswith("TOTAL") and causas.iloc[-1]["USD"] == "-80,315.00"
    assert any("Archivo" in t.columns and "Fila" in t.columns for t in tablas)
    assert any(e.value.startswith("PROVISIONAL") for e in at.error)
    assert any("Sin explicar" in str(t.get("Causa", "")) for t in tablas if "Causa" in t.columns)


def test_sin_periodo_previo_avisa():
    at = app("2026-10", None)
    assert any("primer periodo" in i.value for i in at.info)
