"""Diagnostico y fichas: toda ficha explica, ubica, cuantifica y propone una accion humana; nunca corrige."""
import re
from decimal import ROUND_HALF_UP, Decimal

import pytest
from streamlit.testing.v1 import AppTest

from conftest import DATA, KEY, ROOT
from nexus import diagnostico as DG
from nexus.pipeline import run
from test_matriz_errores import make, row

D = Decimal
PERSONAS = re.compile(r"\b(empleado|contador|usuario|persona que|culpa|negligen|descuid|incompeten|se equivoc|"
                      r"digitador|capturista|analista)", re.I)


@pytest.fixture(scope="module")
def res():
    return run(DATA, ic_tolerance_usd=KEY["tolerancia_intercompania_usd"], profiles_dir=ROOT / "profiles")


@pytest.fixture(scope="module")
def fichas(res):
    return DG.diagnosticar(res)


def balance(tmp_path, rows, cur="USD"):
    res, _ = make(tmp_path, rows, periods=("2026-10",), a_cur=cur)
    f = [x for x in DG.diagnosticar(res) if x.tipo == DG.BALANCE]
    assert len(f) == 1, f"se esperaba 1 ficha de balance, hay {len(f)}"
    return f[0], res


# ================================================================== todo hallazgo de la clave tiene ficha
TIPO_DE_ERROR = {"moneda_invalida": DG.MONEDA_NO_RECONOCIDA, "total_no_cuadra": DG.TOTAL_DESC,
                 "duplicado_confirmado": DG.DUPLICADO, "posible_duplicado": DG.DUPLICADO,
                 "cuenta_sin_mapear": DG.SIN_MAPEAR, "diferencia_intercompania": DG.INTERCOMPANIA,
                 "importe_atipico": DG.MONEDA_SOSPECHOSA, "signo_invertido": DG.SIGNO, "mes_faltante": DG.MES_FALTANTE}


def test_todo_hallazgo_del_answer_key_tiene_ficha(res, fichas):
    for e in KEY["errores_sembrados"]:
        tipo = TIPO_DE_ERROR[e["tipo"]]
        if e["tipo"] == "mes_faltante":
            u = e["ubicaciones"][0]
            assert any(f.tipo == tipo and f.company_id == u["company_id"] and f.period == u["period"] for f in fichas)
            continue
        for loc in e["ubicaciones"]:
            assert any(f.tipo == tipo and any(d.file == loc["file"] and d.row == loc["row"] and d.sheet == loc.get("sheet")
                                              for d in f.donde) for f in fichas), (e["tipo"], loc)


def test_las_fichas_traen_todas_las_secciones_y_la_causa_es_probable(fichas):
    assert fichas
    for f in fichas:
        for campo in ("que_paso", "por_que_importa", "impacto_utilidad", "causa_probable", "accion"):
            assert getattr(f, campo).strip(), (f.ficha_id, campo)
        assert f.donde, f.ficha_id
        assert "probable" in f.causa_probable.lower() or "causa no identificada" in f.causa_probable.lower(), f.ficha_id


def test_las_fichas_nunca_atribuyen_el_error_a_personas(fichas):
    for f in fichas:
        for campo in ("que_paso", "por_que_importa", "impacto_utilidad", "causa_probable", "accion"):
            assert not PERSONAS.search(getattr(f, campo)), (f.ficha_id, campo, getattr(f, campo))


def test_las_fichas_estan_ordenadas_por_impacto(fichas):
    imp = [f.impacto_usd for f in fichas if f.impacto_usd is not None]
    assert imp == sorted(imp, reverse=True)
    assert all(f.impacto_usd is None for f in fichas[len(imp):])                       # los n/c al final
    assert [f.ficha_id for f in fichas] == [f"FCH-{i:03d}" for i in range(1, len(fichas) + 1)]


def test_la_discrepancia_intercompania_es_una_sola_ficha_con_ambos_lados(fichas):
    ic = [f for f in fichas if f.tipo == DG.INTERCOMPANIA]
    assert len(ic) == 1 and ic[0].impacto_usd == D("2000")
    assert "operación (la venta)" in ic[0].que_paso and "saldo (cuenta por cobrar y por pagar)" in ic[0].que_paso
    assert len(ic[0].donde) == 4                                                       # venta, compra, CxC y CxP
    assert "+2,000.00" in ic[0].impacto_utilidad


def test_contador_por_tipo_suma_las_fichas(fichas):
    c = DG.contador_por_tipo(fichas)
    assert sum(c.values()) == len(fichas) and c[DG.DUPLICADO] == 2


# ================================================================== moneda "Q"
def test_moneda_q_es_probable_alias_de_gtq_pero_requiere_aprobacion_y_no_se_convierte(res, fichas):
    loc = next(e for e in KEY["errores_sembrados"] if e["tipo"] == "moneda_invalida")["ubicaciones"][0]
    f = next(f for f in fichas if f.tipo == DG.MONEDA_NO_RECONOCIDA)
    txt = f.causa_probable + " " + f.accion
    assert "«Q»" in f.causa_probable and "Probable alias de GTQ" in f.causa_probable
    assert "aprobación humana" in f.causa_probable and "NO convierte" in f.causa_probable
    assert "una persona" in f.accion.lower()
    r = next(r for r in res.records if r.source_file == loc["file"] and r.source_row == loc["row"])
    assert r.status == "BLOCKED" and r.amount_usd is None and r.currency == "Q"           # NEXUS no la convirtio
    import csv
    with open(DATA / "tasas.csv", encoding="utf-8") as fh:
        tasa = next(D(x["usd_por_unidad_local"]) for x in csv.DictReader(fh)
                    if x["periodo"] == loc["period"] and x["moneda"] == "GTQ")
    assert f.impacto_usd == D(loc["amount_local"]) * tasa and f.impacto_estimado          # 220,000 x 0.125 = 27,500
    assert res.periods[loc["period"]].summary["gastos_operativos"] is not None
    assert "27,500.00" in f.por_que_importa and "no aplicada" in f.por_que_importa


def test_moneda_desconocida_sin_alias_no_sugiere_nada(tmp_path):
    res, _ = make(tmp_path, [row("2026-10", "Ventas", 100, "XYZ")], periods=("2026-10",))
    f = next(x for x in DG.diagnosticar(res) if x.tipo == DG.MONEDA_NO_RECONOCIDA)
    assert "alias" not in f.causa_probable.lower() and f.impacto_usd is None and "probable" in f.causa_probable.lower()


# ================================================================== diagnostico de balance (a mano)
def test_balance_8000_con_un_registro_de_8000_omitido(tmp_path):
    """Activo 20,000 - (pasivo 6,000 + patrimonio 6,000) = D = 8,000. Hay un registro de 8,000 que quedo fuera del
    balance (cuenta sin equivalencia): candidata 1 (importe = D) y 4 (registros fuera suman D)."""
    f, _ = balance(tmp_path, [row("2026-10", "Caja", 20000, "USD"), row("2026-10", "Proveedores", 6000, "USD"),
                              row("2026-10", "Capital", 6000, "USD"), row("2026-10", "Cuenta rara", 8000, "USD")])
    assert f.diferencia == D("8000") and f.causa_identificada
    assert f.candidatos[0].orden == 1 and f.candidatos[0].tipo == "REGISTRO_IGUAL_A_D"
    assert [u.account_local for u in f.candidatos[0].registros] == ["Cuenta rara"]
    assert any(c.orden == 4 and c.tipo == "REGISTROS_FUERA" for c in f.candidatos)
    assert "Causa candidata más probable" in f.causa_probable and "hipótesis" in f.causa_probable


def test_balance_8000_por_un_registro_de_4000_con_signo_invertido(tmp_path):
    """Correcto: caja 16,000 = proveedores +4,000 + capital 12,000. Con proveedores -4,000: D = 16,000 - 8,000 = 8,000
    y 4,000 x 2 = 8,000."""
    f, _ = balance(tmp_path, [row("2026-10", "Caja", 16000, "USD"), row("2026-10", "Proveedores", -4000, "USD"),
                              row("2026-10", "Capital", 12000, "USD")])
    assert f.diferencia == D("8000")
    c = next(c for c in f.candidatos if c.orden == 2)
    assert c.tipo == "SIGNO_INVERTIDO" and [(u.account_local, u.importe) for u in c.registros] == \
        [("Proveedores", D("-4000"))]
    assert not any(c.orden == 1 for c in f.candidatos)                                # ningun registro de 8,000


def test_balance_8000_por_un_duplicado_de_8000(tmp_path):
    """Tres cajas de 8,000 (dos con la misma fecha y contraparte, sin ID = posible duplicado), proveedores 8,000 y
    capital 8,000: activo 24,000 - 16,000 = D = 8,000."""
    f, res = balance(tmp_path, [row("2026-10", "Caja", 8000, "USD", cp="Banco X"),
                                row("2026-10", "Caja", 8000, "USD", cp="Banco X"),
                                row("2026-10", "Caja", 8000, "USD", cp="Banco Y"),
                                row("2026-10", "Proveedores", 8000, "USD"), row("2026-10", "Capital", 8000, "USD")])
    assert f.diferencia == D("8000")
    c = next(c for c in f.candidatos if c.orden == 3)
    assert c.tipo == "DUPLICADO" and len(c.registros) == 2 and {u.account_local for u in c.registros} == {"Caja"}
    assert [x.orden for x in f.candidatos] == sorted(x.orden for x in f.candidatos)   # en orden


def test_balance_sin_causa_identificada_muestra_los_registros_mas_cercanos(tmp_path):
    """D = 20,000 - 12,000 = 8,000 y ningun registro, doble, duplicado o fuera de balance coincide."""
    f, _ = balance(tmp_path, [row("2026-10", "Caja", 20000, "USD"), row("2026-10", "Proveedores", 5000, "USD"),
                              row("2026-10", "Capital", 7000, "USD")])
    assert f.diferencia == D("8000") and f.causa_identificada is False and f.candidatos == []
    assert "Causa no identificada" in f.causa_probable
    assert [u.importe for u in f.cercanos] == [D("7000"), D("5000"), D("20000")]      # ordenados por cercania a 8,000


def test_balance_por_diferencia_de_tasa(tmp_path):
    """Caja 80,000 GTQ = 10,000 USD; proveedores 40,000 GTQ = 5,000; capital 40,000 marcado MXN = 2,000. D = 3,000
    = 40,000 x (0.125 - 0.05): el capital esta valorado con la tasa de otra moneda."""
    f, _ = balance(tmp_path, [row("2026-10", "Caja", 80000, "GTQ"), row("2026-10", "Proveedores", 40000, "GTQ"),
                              row("2026-10", "Capital", 40000, "MXN")], cur="GTQ")
    assert f.diferencia == D("3000")
    c = next(c for c in f.candidatos if c.orden == 5)
    assert c.tipo == "DIFERENCIA_DE_TASA" and "Capital" in {u.account_local for u in c.registros}   # y su espejo


def test_balance_en_el_grupo_de_prueba_no_hay_ficha(fichas):
    assert not [f for f in fichas if f.tipo == DG.BALANCE]                            # el balance cuadra por construccion


# ================================================================== el diagnostico no modifica nada
def test_diagnosticar_no_modifica_el_resultado(res):
    antes = {r.record_id: (r.status, r.amount_usd, list(r.flags)) for r in res.records}
    resumen = {p: dict(pr.summary) for p, pr in res.periods.items()}
    DG.diagnosticar(res)
    assert antes == {r.record_id: (r.status, r.amount_usd, list(r.flags)) for r in res.records}
    assert resumen == {p: pr.summary for p, pr in res.periods.items()}


# ================================================================== interfaz
def test_la_pestana_hallazgos_muestra_contador_y_fichas():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120).run()
    assert not at.exception, at.exception
    assert "Hallazgos" in [t.label for t in at.tabs]
    # octubre: duplicado confirmado, cuenta sin mapear, signo invertido
    etiquetas = " | ".join(e.label for e in at.expander if e.label.startswith("FCH-"))
    for nombre in ("Duplicado", "Cuenta sin mapear", "Signo invertido"):
        assert nombre in etiquetas
    assert any(m.label == "Duplicado" and m.value == "1" for m in at.metric)
    at.sidebar.radio[0].set_value("2026-11").run()
    assert not at.exception
    texto = " ".join(m.value for m in at.markdown)
    assert "Probable alias de GTQ" in texto and "aprobación humana" in texto
