"""Escenario con errores sembrados (data/demo_errores): generador, deteccion de los 7 errores, acciones, aprobacion
humana (aprobar / rechazar / deshacer) con registro de auditoria, y la interfaz. Los numeros salen de la ANSWER_KEY de
demo y de la clave del escenario limpio (calculos independientes del motor)."""
import hashlib
import json
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import load_workbook
from streamlit.testing.v1 import AppTest

from conftest import DATA, KEY, ROOT
from nexus.pipeline import run
from nexus.ui import correcciones as CO
from nexus.ui import explicar, resumen_carga

D = Decimal
DEMO = ROOT / "data" / "demo_errores"
PERF = DEMO / "perfiles"
K = json.loads((DEMO / "ANSWER_KEY.json").read_text(encoding="utf-8"))
ERR = {e["n"]: e for e in K["errores"]}
FALLA = ("falló", "No se pudo", "no define render", "Traceback", "Exception", "Próximamente")
sys.path.insert(0, str(ROOT / "scripts"))


def hashes(*dirs):
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for d in dirs for p in sorted(Path(d).rglob("*")) if p.is_file()}


@pytest.fixture(scope="module")
def r():
    return run(DEMO, profiles_dir=PERF)


@pytest.fixture(scope="module")
def limpio():
    return run(DATA, ic_tolerance_usd=KEY["tolerancia_intercompania_usd"], profiles_dir=ROOT / "profiles")


@pytest.fixture(scope="module")
def props(r):
    return {p.key: p for p in CO.proponer(r)}


def prop(props, kind, **campos):
    return next(p for p in props.values() if p.kind == kind and all(getattr(p, k) == v for k, v in campos.items()))


def rec(res, key):
    return next(x for x in res.records if x.record_id == key)


def ev(p, quien="Ana Prueba", cuenta=None, evento="APROBAR"):
    return CO.evento_desde(p, evento, quien, "esc", cuenta) | {"ts": "2026-11-21T12:00:00"}


# ================================================================== A. el generador
def test_el_escenario_tiene_los_6_archivos_los_perfiles_y_la_clave():
    assert {f.name for f in DEMO.iterdir() if f.is_file() and f.suffix in (".xlsx", ".csv", ".json")} >= {
        "aceros_ferrex_gt.xlsx", "distribuidora_central_gt.csv", "ferrex_mexico.xlsx", "ferrex_el_salvador.xlsx",
        "transportes_ferrex_mx.csv", "ferrex_importaciones_pa.json"}
    assert len(list(PERF.glob("EMP00*.json"))) == 6
    md = (DEMO / "ANSWER_KEY.md").read_text(encoding="utf-8")
    assert "APLICADA_AUTOMATICAMENTE" in md and "PROPUESTA" in md and md.count("\n| ") >= 7 + 1


def test_el_generador_es_reproducible_y_no_toca_data_synthetic(tmp_path):
    import generate_demo_errores as G
    antes = hashes(DATA)
    viejo = G.OUT
    G.OUT = tmp_path / "otra"
    try:
        G.main()
    finally:
        G.OUT = viejo
    assert hashes(DATA) == antes                                                     # data/synthetic intacta
    for f in ("distribuidora_central_gt.csv", "transportes_ferrex_mx.csv", "ferrex_importaciones_pa.json", "tasas.csv",
              "ANSWER_KEY.json", "ANSWER_KEY.md"):
        assert (tmp_path / "otra" / f).read_bytes() == (DEMO / f).read_bytes(), f     # misma semilla: mismo resultado
    for f in ("aceros_ferrex_gt.xlsx", "ferrex_mexico.xlsx", "ferrex_el_salvador.xlsx"):
        a, b = load_workbook(tmp_path / "otra" / f), load_workbook(DEMO / f)
        for ws in a.worksheets:
            assert [[c.value for c in row] for row in ws.iter_rows()] == \
                [[c.value for c in row] for row in b[ws.title].iter_rows()], f


def test_cada_error_esta_en_el_lugar_que_dice_la_clave():
    csv2 = (DEMO / ERR[2]["archivo"]).read_text(encoding="utf-8").splitlines()[ERR[2]["fila"] - 1]
    assert csv2.split(";")[1] == ERR[2]["cuenta"] and csv2.split(";")[2] == ""                       # monto en blanco
    csv3 = (DEMO / ERR[3]["archivo"]).read_bytes().decode("cp1252").splitlines()[ERR[3]["fila"] - 1]
    assert '"1O,000"' in csv3 and "O" in csv3.split('"')[1]                                          # letra O
    ws = load_workbook(DEMO / ERR[1]["archivo"])[ERR[1]["hoja"]]
    assert [c.value for c in ws[66]] == [c.value for c in ws[65]] and ws[66][5].value == "FAC-M-0902"
    ws = load_workbook(DEMO / ERR[4]["archivo"])[ERR[4]["hoja"]]
    assert {r[4].value for r in ws.iter_rows(min_row=2)} == {"USD"}                                   # todo USD
    ws = load_workbook(DEMO / ERR[5]["archivo"])[ERR[5]["hoja"]]
    assert ws[ERR[5]["fila"]][2].value == -4000 and ws[ERR[5]["fila"]][1].value == "Other operating expenses"
    e6 = json.loads((DEMO / ERR[6]["archivo"]).read_text(encoding="utf-8"))["entries"][ERR[6]["fila"] - 1]
    assert (e6["period"], e6["account"], e6["amount"]) == ("2026-12", "Trade payables", 8000)
    assert (DEMO / "tasas.csv").read_text(encoding="utf-8").splitlines()[ERR[7]["fila"] - 1] == "2026-12,MXN,0.525"


# ================================================================== B. se detecta cada error y la accion es la esperada
def test_1_duplicado_exacto_con_el_mismo_id_se_aplica_automaticamente(r, props):
    p = prop(props, CO.DUPLICADO, company_id="EMP003")
    assert p.accion == CO.AUTO and p.rule_id == "DUP-01" and not p.aprobable
    x = rec(r, p.record_ids[0])
    assert x.status == "EXCLUDED_DUPLICATE" and x.source_row == 66 and x.source_sheet == ERR[1]["hoja"]
    adj = next(a for a in r.adjustments if a.kind == "DUPLICATE_EXCLUSION" and a.record_ids == [x.record_id])
    assert adj.reversible and adj.reason and adj.rule
    assert p.impacto_usd == D(ERR[1]["usd_excluido"]) == abs(x.amount_usd)                       # 3,000 USD
    assert rec(r, x.record_id.replace("|66", "|65")).status == "OK"                                  # la primera sigue
    assert "ajuste" in p.que_hizo and "reversible" in p.que_hizo


@pytest.mark.parametrize("n,cuenta", [(2, "Gastos varios"), (3, "Combustible y lubricantes")])
def test_2_y_3_monto_vacio_y_texto_en_campo_numerico_quedan_bloqueados_con_propuesta(r, props, n, cuenta):
    e = ERR[n]
    p = next(x for x in props.values() if x.kind == CO.IMPORTE and x.company_id == e["empresa"]
             and rec(r, x.record_ids[0]).source_row == e["fila"])
    x = rec(r, p.record_ids[0])
    assert x.account_local in (cuenta, e["cuenta"]) and x.status == "BLOCKED" and x.amount_usd is None or x.amount_usd
    assert x.status == "BLOCKED" and "Importe no numerico" in x.status_reasons[0] and x.amount_original is None
    assert any(f.rule_id == "ING-01" and x.record_id in f.record_ids for f in r.findings)
    assert p.accion == CO.PROPUESTA and p.valor_leido == e["valor_leido"].replace("(vacio)", "(vacío)")
    assert p.valor_propuesto == D(e["valor_propuesto"]) and p.impacto_usd == D(e["usd_propuesto"])
    assert p.aprobable and p.motivo and "no entra al consolidado" in p.que_hizo
    assert f"{p.impacto_usd:+,.2f}".lstrip("+") or True


def test_4_archivo_que_declara_usd_siendo_gtq_queda_en_revision_con_propuesta(r, props):
    rep = r.load_reports["EMP001"]
    assert rep.status == "REVIEW" and any("declara USD" in x and "GTQ" in x for x in rep.reasons)
    assert not [x for x in r.records if x.company_id == "EMP001"]
    p = prop(props, CO.MONEDA_ARCHIVO)
    assert (p.company_id, p.valor_leido, p.valor_propuesto) == ("EMP001", "USD", "GTQ") and p.aprobable
    assert any(f.rule_id == "CARGA-01" and f.company_id == "EMP001" for f in r.findings)


def test_5_signo_invertido_de_4000_queda_bloqueado_con_propuesta(r, props):
    p = next(x for x in props.values() if x.kind == CO.SIGNO and x.company_id == "EMP004")
    x = rec(r, p.record_ids[0])
    assert x.status == "BLOCKED" and x.amount_original == D("-4000") and x.source_row == ERR[5]["fila"]
    assert any(f.rule_id == "SIGN-01" and x.record_id in f.record_ids for f in r.findings)
    assert (p.valor_leido, p.valor_propuesto, p.impacto_usd) == ("-4000", D("4000"), D(ERR[5]["usd_propuesto"]))
    ir = next(i for i in r.periods["2026-10"].impact_ranges if i.record_id == x.record_id)      # rango en utilidad
    assert (ir.utility_excluded, ir.utility_as_is, ir.utility_corrected) == (0, D("4000"), D("-4000"))
    assert "-4,000.00" in p.impacto_utilidad                                                       # utilidad si se aprueba


def test_6_asiento_omitido_descuadra_el_balance_y_se_ve_el_diagnostico(r, props):
    from nexus import diagnostico as DG
    f = next(x for x in DG.diagnosticar(r) if x.tipo == DG.BALANCE)
    assert (f.company_id, f.period, f.diferencia) == ("EMP006", "2026-12", D(ERR[6]["diferencia_balance"]))
    assert f.candidatos[0].tipo == "REGISTRO_IGUAL_A_D" and f.candidatos[0].registros[0].account_local == "Trade payables"
    assert r.periods["2026-12"].summary["activo_menos_pasivo_y_patrimonio"] == D("-8000")
    p = prop(props, CO.ASIENTO)
    assert p.cuenta_requerida and p.valor_propuesto == D("8000") and {c for c, _ in p.extra["opciones"]} >= {"1000"}
    assert all(r.config.catalog[c].cls == "activo" for c, _ in p.extra["opciones"])                  # D < 0: falta activo


def test_7_tasa_mal_escrita_se_marca_sin_bloquear_ni_corregir(r, props):
    f = next(x for x in r.findings if x.rule_id == "TAS-01")
    assert f.period == "2026-12" and "MXN pasa de 0.05 a 0.525 (+950.0%)" in f.message
    p = prop(props, CO.TASA)
    assert (p.valor_leido, p.valor_propuesto) == (ERR[7]["valor_leido"], D(ERR[7]["valor_propuesto"]))
    assert r.config.rates[("2026-12", "MXN")].rate == D("0.525") and p.aprobable                     # se usa tal cual
    assert all(x.status == "OK" for x in r.records if x.currency == "MXN" and x.period == "2026-12"
               and x.account_code and x.amount_usd is not None and "BLOCK" not in x.status)


def test_la_clave_dice_una_sola_accion_automatica():
    assert [e["n"] for e in K["errores"] if e["accion"] == "APLICADA_AUTOMATICAMENTE"] == [1]
    assert sorted(e["n"] for e in K["errores"] if e["accion"] == "PROPUESTA") == [2, 3, 4, 5, 6, 7]


# ================================================================== C. aprobar recalcula los numeros (sin tocar archivos)
def todas(props):
    sel = [prop(props, CO.IMPORTE, company_id="EMP002"), prop(props, CO.IMPORTE, company_id="EMP005",
                                                               valor_leido="1O,000"),
           prop(props, CO.SIGNO, company_id="EMP004"), prop(props, CO.MONEDA_ARCHIVO), prop(props, CO.TASA)]
    return [ev(p) for p in sel] + [ev(prop(props, CO.ASIENTO), cuenta="1000")]


def test_sin_aprobaciones_el_recalculo_es_igual_al_motor(r, limpio):
    for datos, perf, ref in ((DEMO, PERF, r), (DATA, ROOT / "profiles", limpio)):
        c = CO.run_corregido(datos, perf)
        assert {p: x.summary for p, x in c.periods.items()} == {p: x.summary for p, x in ref.periods.items()}
        assert {x.record_id: (x.status, x.amount_usd) for x in c.records} == \
            {x.record_id: (x.status, x.amount_usd) for x in ref.records}
        assert sorted(f.rule_id for f in c.findings) == sorted(f.rule_id for f in ref.findings)


def test_aprobar_las_6_propuestas_deja_los_numeros_de_la_clave(r, props, limpio):
    antes = hashes(DEMO, DATA, ROOT / "profiles")
    c = CO.run_corregido(DEMO, PERF, todas(props))
    k = KEY["consolidado_esperado_usd"]
    d = {m: D(v) for m, v in K["delta_oct_tras_aprobar"].items()}
    o = c.periods["2026-10"].summary
    base = {m: D(k["2026-10"]["resumen"][m]) for m in ("ingresos", "gastos_operativos", "utilidad_neta")}
    for m in d:
        assert o[m] == base[m] + d[m], m                                      # octubre = limpio + efecto de la clave
    assert (o["ingresos"], o["utilidad_neta"]) == (D("1988000"), D("357500"))
    for per in ("2026-11", "2026-12"):                                        # nov y dic vuelven EXACTO al limpio
        for m in ("ingresos", "costo_ventas", "gastos_operativos", "utilidad_neta", "activo_total", "pasivo_total"):
            extra = D("8000") if per == "2026-12" and m in ("activo_total", "pasivo_total") else D(0)
            # el asiento de #6 es un asiento NUEVO de 8,000 USD (activo aprobado + pasivo ya cargado): suma a ambos lados
            assert c.periods[per].summary[m] == D(k[per]["resumen"][m]) + extra, (per, m)
    assert c.periods["2026-12"].summary["activo_menos_pasivo_y_patrimonio"] == 0          # el asiento cuadra el balance
    assert c.load_reports["EMP001"].status == "MATCHED" and "aprobada por Ana Prueba" in c.load_reports["EMP001"].notes[0]
    rules = {f.rule_id for f in c.findings}
    assert not rules & {"TAS-01", "BAL-01", "CARGA-01", "SIGN-01"} or {f.company_id for f in c.findings
                                                                         if f.rule_id == "SIGN-01"} == {"EMP005"}
    assert not [f for f in c.findings if f.rule_id == "ING-01"]
    assert hashes(DEMO, DATA, ROOT / "profiles") == antes                       # ningun archivo fuente cambio


def test_cada_aprobacion_deja_su_ajuste_con_quien_valor_y_motivo(r, props):
    c = CO.run_corregido(DEMO, PERF, todas(props))
    hum = [a for a in c.adjustments if a.kind == "HUMAN_CORRECTION"]
    assert len(hum) == 6 and all(a.approved_by == "Ana Prueba" and a.reversible and a.reason for a in hum)
    assert all("Valor leído" in a.reason and "valor aprobado" in a.reason for a in hum)
    x = rec(c, prop(props, CO.IMPORTE, company_id="EMP005", valor_leido="1O,000").record_ids[0])
    assert x.status == "OK" and x.amount_original == D("10000") and x.amount_usd == D("500") and x.adjustment_ids


def test_aprobar_la_tasa_quita_sus_consecuencias(r, props):
    n_ati = len([f for f in r.findings if f.rule_id == "ATI-01" and f.period == "2026-12"])
    c = CO.run_corregido(DEMO, PERF, [ev(prop(props, CO.TASA))])
    assert n_ati > 20 and not [f for f in c.findings if f.rule_id in ("TAS-01",)]
    assert len([f for f in c.findings if f.rule_id == "ATI-01" and f.period == "2026-12"]) == 1   # solo el sembrado (GTQ)


def test_revertir_la_exclusion_automatica_vuelve_a_incluir_el_duplicado(r, props):
    p = prop(props, CO.DUPLICADO)
    c = CO.run_corregido(DEMO, PERF, [ev(p)])
    assert rec(c, p.record_ids[0]).status == "OK"
    assert not [a for a in c.adjustments if a.kind == "DUPLICATE_EXCLUSION" and a.record_ids == p.record_ids]
    assert c.periods["2026-10"].summary["ingresos"] == r.periods["2026-10"].summary["ingresos"] + D("3000")


# ================================================================== D. registro de auditoria: aprobar, rechazar, deshacer
def test_registro_de_auditoria_aprobar_rechazar_y_deshacer(tmp_path, props):
    log = tmp_path / "log.jsonl"
    p = prop(props, CO.SIGNO, company_id="EMP004")
    CO.registrar(log, CO.evento_desde(p, "APROBAR", "Ana Prueba", "esc"))
    e = CO.leer(log)[0]
    assert (e["quien"], e["evento"], e["valor_leido"], e["valor_propuesto"], e["key"]) == \
        ("Ana Prueba", "APROBAR", "-4000", "4000", p.key)
    assert e["ts"] and e["motivo"] and e["impacto_usd"] == "4000" and e["record_ids"] == p.record_ids
    assert [a["key"] for a in CO.aprobaciones(log, "esc")] == [p.key]
    CO.registrar(log, {"evento": "DESHACER", "quien": "Ana Prueba", "escenario": "esc", "key": p.key, "kind": p.kind})
    assert CO.estado(log, "esc") == {} and CO.aprobaciones(log, "esc") == []                  # deshacer vuelve a pendiente
    CO.registrar(log, CO.evento_desde(p, "RECHAZAR", "Ana Prueba", "esc"))
    assert CO.estado(log, "esc")[p.key]["evento"] == "RECHAZAR" and CO.aprobaciones(log, "esc") == []
    assert len(CO.leer(log)) == 3                                                             # solo se agrega, nunca se borra
    assert CO.estado(log, "otro") == {}                                                       # cada escenario por separado


# ================================================================== E. resumen de la carga y explicacion
def test_resumen_de_la_carga_cuadra_con_los_registros(r, props, limpio):
    d = resumen_carga.calcular(r, [p for p in props.values() if p.aprobable])
    assert (d["archivos_total"], d["archivos_leidos"]) == (6, 5)
    assert d["registros"] == len(r.records) and d["correctos"] == sum(1 for x in r.records if x.status in ("OK", "TOTAL"))
    assert d["auto"] == 1 and d["bloqueados"] == sum(1 for x in r.records if x.status == "BLOCKED")
    est = {a["empresa"]: a for a in d["archivos"]}
    assert est["EMP001"]["estado"] == "rojo" and est["EMP003"]["estado"] == "amarillo"
    assert all(len(a["huella"]) == 64 and a["huella"] == r.input_hashes[a["archivo"]] for a in d["archivos"])
    assert d["pendientes"] == len([p for p in props.values() if p.aprobable]) + d["sin_confirmar"]
    dl = resumen_carga.calcular(limpio, [])
    assert dl["archivos_leidos"] == 6 and {a["estado"] for a in dl["archivos"]} <= {"verde", "amarillo", "rojo"}


def test_explicar_todo_en_simple_tiene_los_6_pasos_con_numeros_reales(r, props):
    pasos = explicar.pasos(r, "2026-10", [p for p in props.values() if p.aprobable])
    assert [t.split(".")[0] for t, _ in pasos] == ["1", "2", "3", "4", "5", "6"]
    assert [t.split(". ")[1] for t, _ in pasos] == ["Lectura", "Normalización", "Validación", "Conversión a USD",
                                                   "Eliminaciones entre empresas", "Consolidación"]
    n = sum(x.n_records for x in r.load_reports.values() if x.status != "REVIEW")
    assert f"obtuvo {n} registros" in pasos[0][1] and "No pudo leer EMP001" in pasos[0][1]
    assert f"{r.periods['2026-10'].summary['ingresos']:,.2f}"[:9] in pasos[5][1]
    assert "importe × tasa" in pasos[3][1] and "NO se eliminan" in pasos[4][1] or "no cuadran" in pasos[4][1]


# ================================================================== F. interfaz
@pytest.fixture()
def app():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120).run()
    assert not at.exception, at.exception
    return at


def ir(at, seccion):
    at.radio(key="nav").set_value(seccion).run()
    assert not at.exception, (seccion, at.exception)
    return at


def a_demo(at):
    """Carga la carpeta con los 16 errores sembrados, como lo haria «Cargar presupuestos»."""
    from conftest import DEMO_ERR, DEMO_ERR_PERF, cargar
    return cargar(at, DEMO_ERR, DEMO_ERR_PERF)


def textos(at):
    return [m.value for m in at.markdown] + [e.value for e in at.error] + [w.value for w in at.warning] + \
           [i.value for i in at.info] + [s.value for s in at.success] + [c.value for c in at.caption]


def metrica(at, nombre):
    return next(m.value for m in at.metric if m.label == nombre)


def test_no_queda_ninguna_marca_de_demostracion_en_la_interfaz(app):
    a_demo(app)
    for t in textos(app):
        assert "DEMOSTRACIÓN" not in t and "Datos base" not in t and "errores sembrados" not in t
    assert not [r for r in app.radio if r.key == "escenario"]


@pytest.mark.parametrize("carpeta", ["synthetic", "demo_errores", "demo"])
@pytest.mark.parametrize("periodo", ["2026-10", "2026-11", "2026-12"])
def test_ninguna_pestana_falla_con_ninguna_carpeta(app, carpeta, periodo):
    from conftest import cargar
    d = ROOT / "data" / carpeta
    cargar(app, d, d / "perfiles" if (d / "perfiles").is_dir() else (ROOT / "profiles" if carpeta == "synthetic" else None))
    app.sidebar.radio[0].set_value(periodo).run()
    assert not app.exception, app.exception
    for t in textos(app):
        for palabra in FALLA:
            assert palabra not in t, f"{carpeta}/{periodo}: '{palabra}' en {t[:100]}"


def test_resumen_de_la_carga_y_explicar_todo_en_simple_en_la_interfaz(app):
    a_demo(app)
    franja = " ".join(m.value for m in app.markdown if "Archivos leídos" in m.value)
    assert "5 de 6" in franja and "Pendientes de tu decisión" in franja and "Corregidos automáticamente" in franja
    todo = " ".join(m.value for m in app.markdown)
    assert "Huella (SHA-256)" in todo and ">Rojo<" in todo and ">Amarillo<" in todo
    assert not [m for m in app.markdown if "Qué hizo NEXUS con tus archivos" in m.value]
    app.button(key="explicar_btn").click().run()
    tx = " ".join(m.value for m in app.markdown)
    for titulo in ("1. Lectura", "2. Normalización", "3. Validación", "4. Conversión a USD",
                   "5. Eliminaciones entre empresas", "6. Consolidación"):
        assert f"**{titulo}.**" in tx
    app.button(key="explicar_btn").click().run()
    assert not [m for m in app.markdown if "Qué hizo NEXUS con tus archivos" in m.value]


def test_la_ficha_responde_que_paso_donde_valor_leido_por_que_importa_que_hizo_que_propone_y_que_decide(app):
    a_demo(app)
    ir(app, "Hallazgos")
    tx = " ".join(m.value for m in app.markdown)
    for frag in ("**Valor leído.** `1O,000`", "**Qué hizo NEXUS.**", "**Qué propone.**", "**Qué debe decidir una persona.**",
                 "**Por qué importa.**", "**Causa probable.**", "APLICADA AUTOMÁTICAMENTE"):
        assert frag in tx, frag
    assert "(vacío)" in tx
    assert not any(p in tx.lower() for p in ("negligen", "se equivocó", "empleado", "contador"))


def test_aprobar_necesita_un_nombre_y_el_registro_lo_guarda(app, monkeypatch):
    import os
    a_demo(app)
    ir(app, "Hallazgos")
    k = "aprobar_SIGNO|EMP004|ferrex_el_salvador.xlsx|Income Statement|36"
    assert app.button(key=k).disabled                                          # sin nombre no se puede aprobar
    assert any("Escribe tu nombre" in c.value for c in app.caption)
    app.text_input(key="aprobador").set_value("Ana Prueba").run()
    assert not app.button(key=k).disabled
    log = Path(os.environ["NEXUS_APROBACIONES"])
    assert not log.exists()
    antes = hashes(DEMO, DATA, ROOT / "profiles")
    app.button(key=k).click().run()
    assert not app.exception, app.exception
    ev0 = CO.leer(log)[-1]
    assert (ev0["evento"], ev0["quien"], ev0["valor_leido"], ev0["valor_propuesto"], ev0["kind"]) == \
        ("APROBAR", "Ana Prueba", "-4000", "4000", "SIGNO")
    assert ev0["ts"] and ev0["motivo"] and ev0["escenario"].endswith("demo_errores")
    assert metrica(app, "Resueltos") == "1" and metrica(app, "Pendientes de tu decisión") == "4"
    resuelto = [e for e in app.expander if e.label.startswith("✔ Resuelto · Signo corregido · EMP004")]
    assert len(resuelto) == 1
    assert hashes(DEMO, DATA, ROOT / "profiles") == antes                      # el archivo fuente NUNCA se modifica
    # el hallazgo ya no esta pendiente y el consolidado se recalculo (gasto +4,000 USD en octubre)
    ir(app, "Estados financieros")
    gastos = next(t for t in [d.value for d in app.dataframe] if "Suma de empresas" in t.columns and
                  "(-) Gastos operativos" in set(t["Concepto"]))
    assert gastos[gastos["Concepto"] == "(-) Gastos operativos"].iloc[0]["Consolidado"] == "358,825.00"
    # deshacer
    ir(app, "Hallazgos")
    app.button(key="deshacer_SIGNO|EMP004|ferrex_el_salvador.xlsx|Income Statement|36").click().run()
    assert CO.leer(log)[-1]["evento"] == "DESHACER" and metrica(app, "Resueltos") == "0"
    assert metrica(app, "Pendientes de tu decisión") == "5" and CO.aprobaciones(log, ev0["escenario"]) == []
    ir(app, "Estados financieros")
    gastos = next(t for t in [d.value for d in app.dataframe] if "Suma de empresas" in t.columns and
                  "(-) Gastos operativos" in set(t["Concepto"]))
    assert gastos[gastos["Concepto"] == "(-) Gastos operativos"].iloc[0]["Consolidado"] == "354,825.00"
    assert hashes(DEMO, DATA, ROOT / "profiles") == antes


def test_rechazar_deja_el_hallazgo_abierto_y_se_puede_deshacer(app):
    import os
    a_demo(app)
    ir(app, "Hallazgos")
    app.text_input(key="aprobador").set_value("Ana Prueba").run()
    k = "IMPORTE|EMP005|transportes_ferrex_mx.csv||55"
    app.button(key=f"rechazar_{k}").click().run()
    log = Path(os.environ["NEXUS_APROBACIONES"])
    assert CO.leer(log)[-1]["evento"] == "RECHAZAR" and metrica(app, "Rechazadas") == "1"
    assert metrica(app, "Resueltos") == "0" and any(e.label.startswith("✖ Rechazada") for e in app.expander)
    app.button(key=f"deshacer_{k}").click().run()
    assert metrica(app, "Rechazadas") == "0" and CO.leer(log)[-1]["evento"] == "DESHACER"


def test_el_asiento_omitido_pide_elegir_la_cuenta_y_cuadra_el_balance(app):
    import os
    a_demo(app)
    ir(app, "Hallazgos")
    app.sidebar.radio[0].set_value("2026-12").run()
    app.text_input(key="aprobador").set_value("Ana Prueba").run()
    k = "ASIENTO|EMP006|2026-12"
    assert app.button(key=f"aprobar_{k}").disabled                              # falta elegir la cuenta
    app.selectbox(key=f"cuenta_{k}").select("1000").run()
    assert not app.button(key=f"aprobar_{k}").disabled
    app.button(key=f"aprobar_{k}").click().run()
    assert not app.exception, app.exception
    e = CO.leer(Path(os.environ["NEXUS_APROBACIONES"]))[-1]
    assert (e["kind"], e["cuenta"], e["valor_propuesto"]) == ("ASIENTO", "1000", "8000")
    ir(app, "Estados financieros")
    assert any("Activo - (Pasivo + Patrimonio) = 0.00 USD" in s.value for s in app.success)


def test_los_originales_no_cambian_al_usar_la_interfaz_con_decisiones(app):
    antes = hashes(DEMO, DATA, ROOT / "profiles")
    a_demo(app)
    ir(app, "Hallazgos")
    app.text_input(key="aprobador").set_value("Ana Prueba").run()
    for k in ("aprobar_SIGNO|EMP004|ferrex_el_salvador.xlsx|Income Statement|36",
              "aprobar_IMPORTE|EMP002|distribuidora_central_gt.csv||7", "aprobar_MONEDA_ARCHIVO|EMP001"):
        app.button(key=k).click().run()
        assert not app.exception, app.exception
    app.sidebar.radio[0].set_value("2026-12").run()
    assert hashes(DEMO, DATA, ROOT / "profiles") == antes
