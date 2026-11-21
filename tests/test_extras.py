"""Extras de la interfaz: simulador, paquete de auditoria, nivel de confianza, ayuda y conexion en app.py."""
import csv
import hashlib
import io
import json
import zipfile
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from conftest import DATA, KEY, ROOT
from nexus import simulator as S
from nexus.audit import build_audit_package
from nexus.confidence import ALTA, BAJA, MEDIA, confidence
from nexus.pipeline import run

D = Decimal
PROFILES = ROOT / "profiles"
PERIODOS = sorted(KEY["consolidado_esperado_usd"])


def q2(d):
    return D(d).quantize(D("0.01"), rounding=ROUND_HALF_UP)


@pytest.fixture(scope="module")
def res():
    return run(DATA, ic_tolerance_usd=KEY["tolerancia_intercompania_usd"], profiles_dir=PROFILES)


# ================================================================== simulador
def test_simulador_a_mano_en_un_grupo_minimo(tmp_path):
    """MXN: 1,000,000 x 0.05 = 50,000 USD -> con +10 % la tasa es 0.055 -> 55,000. GTQ: 80,000 x 0.125 = 10,000 -> -10 % = 9,000."""
    from test_matriz_errores import make, row
    base, d = make(tmp_path, [row("2026-10", "Ventas", 80000, "GTQ")], [row("2026-10", "Ventas", 1000000, "MXN")],
                   periods=("2026-10",))
    assert base.periods["2026-10"].summary["ingresos"] == D("60000")                    # 10,000 + 50,000
    sim = S.simulate(d, d / "profiles", {"MXN": D("10"), "GTQ": D("-10")})
    assert sim.periods["2026-10"].summary["ingresos"] == D("64000")                    # 9,000 + 55,000
    solo_mxn = S.simulate(d, d / "profiles", {"MXN": D("10")})
    assert solo_mxn.periods["2026-10"].summary["ingresos"] == D("65000")               # 10,000 + 55,000
    cmp = S.compare(base, sim, "2026-10", {"MXN": D("10"), "GTQ": D("-10")})
    ing = next(r for r in cmp.summary if r.label == "Ingresos")
    assert (ing.original, ing.simulated, ing.difference) == (D("60000"), D("64000"), D("4000"))
    assert cmp.label == "SIMULACIÓN"


def test_simulador_sobre_el_grupo_de_prueba_igual_a_la_clave(res):
    """4100 (solo MXN: servicios + una venta intercompania MXN-MXN que se elimina) vale 120,000 USD en la clave;
    con MXN +10 % todo escala igual (la eliminacion sigue conciliando) y debe valer 132,000."""
    sim = S.simulate(DATA, PROFILES, {"MXN": D("10")})
    base_4100 = D(KEY["consolidado_esperado_usd"]["2026-10"]["por_cuenta"]["4100"])
    assert base_4100 == D("120000.00")
    assert q2(sim.periods["2026-10"].lines["4100"].amount_usd) == q2(base_4100 * D("1.10")) == D("132000.00")
    # una moneda que no se toca no cambia: la cuenta 4000 de EMP004 (USD) sigue igual en sus registros
    usd_rec = {r.record_id: r.amount_usd for r in res.records if r.company_id == "EMP004" and r.amount_usd}
    assert all(usd_rec[r.record_id] == r.amount_usd for r in sim.records if r.record_id in usd_rec)


def test_simulacion_en_cero_es_igual_al_original(res):
    sim = S.simulate(DATA, PROFILES, {"MXN": D("0"), "GTQ": D("0")})
    for p in PERIODOS:
        assert sim.periods[p].summary == res.periods[p].summary
    cmp = S.compare(res, sim, "2026-10")
    assert all(r.difference == 0 for r in cmp.summary + cmp.indicators)


def test_simulador_recalcula_los_indicadores(res):
    sim = S.simulate(DATA, PROFILES, {"MXN": D("10"), "GTQ": D("-10")})
    cmp = S.compare(res, sim, "2026-10")
    nopat = next(r for r in cmp.indicators if r.label == "NOPAT")
    ebit_b, ebit_s = res.periods["2026-10"].summary["ebit"], sim.periods["2026-10"].summary["ebit"]
    assert nopat.original == ebit_b * D("0.75") and nopat.simulated == ebit_s * D("0.75")
    assert nopat.difference != 0


def test_simulador_no_modifica_datos_ni_archivos_ni_el_original(res):
    antes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for d in (DATA, PROFILES) for p in d.iterdir()
             if p.is_file()}
    resumen = {p: dict(pr.summary) for p, pr in res.periods.items()}
    S.simulate(DATA, PROFILES, {"MXN": D("-10"), "GTQ": D("10")})
    despues = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for d in (DATA, PROFILES) for p in d.iterdir()
               if p.is_file()}
    assert antes == despues and {p: pr.summary for p, pr in res.periods.items()} == resumen


@pytest.mark.parametrize("pct", ["10.5", "-11", "100"])
def test_el_simulador_solo_acepta_de_menos_10_a_mas_10(pct):
    with pytest.raises(ValueError):
        S.scale_factors({"MXN": D(pct)})
    assert S.scale_factors({"MXN": D("10"), "GTQ": D("-10")}) == {"MXN": D("1.1"), "GTQ": D("0.9")}


# ================================================================== paquete de auditoria
@pytest.fixture(scope="module")
def paquete(res):
    return zipfile.ZipFile(io.BytesIO(build_audit_package(res, source_dir=DATA)))


def leer(z, nombre):
    return list(csv.DictReader(io.StringIO(z.read(nombre).decode("utf-8"))))


def test_el_paquete_trae_todos_los_archivos(paquete):
    nombres = set(paquete.namelist())
    assert {"consolidado.csv", "resumen.csv", "ajustes.csv", "alertas.csv", "discrepancias.csv",
            "hashes_sha256.csv", "run.json", "records.csv", "LEEME.txt"} <= nombres
    assert {f"perfiles/EMP00{i}.json" for i in range(1, 7)} <= nombres


def test_el_paquete_contiene_las_cifras_de_answer_key(paquete):
    cons = leer(paquete, "consolidado.csv")
    for p, exp in KEY["consolidado_esperado_usd"].items():
        got = {r["cuenta"]: r["consolidado_usd"] for r in cons if r["periodo"] == p}
        assert got == exp["por_cuenta"], p
        assert {r["estado_periodo"] for r in cons if r["periodo"] == p} == {"PROVISIONAL"}
    resumen = leer(paquete, "resumen.csv")
    for p, exp in KEY["consolidado_esperado_usd"].items():
        for r in resumen:
            if r["periodo"] == p and r["concepto"] in exp["resumen"]:
                assert r["consolidado_usd"] == exp["resumen"][r["concepto"]], (p, r["concepto"])
    naive = KEY["suma_ingenua_sin_eliminar_usd"]["2026-10"]
    assert next(r for r in resumen if r["periodo"] == "2026-10" and r["concepto"] == "ingresos")[
        "suma_ingenua_usd"] == naive["ingresos"]


def test_el_paquete_trae_discrepancias_ajustes_alertas_perfiles_y_hashes(paquete, res):
    disc = leer(paquete, "discrepancias.csv")
    assert {(d["referencia"], d["periodo"], d["diferencia_usd"]) for d in disc} == \
        {(d["reference"], d["period"], d["difference_usd"]) for d in KEY["discrepancias_esperadas"]}
    adj = leer(paquete, "ajustes.csv")
    assert {a["tipo"] for a in adj} == {"IC_ELIMINATION", "DUPLICATE_EXCLUSION"}
    esperados = sum(len(e["seller_rows"]) + len(e["buyer_rows"]) for e in KEY["eliminaciones_esperadas"])
    assert len([a for a in adj if a["tipo"] == "IC_ELIMINATION"]) == esperados        # un ajuste por registro eliminado
    assert all(a["reversible"] == "True" for a in adj if a["tipo"] == "DUPLICATE_EXCLUSION")
    reglas = {a["regla"] for a in leer(paquete, "alertas.csv")}
    assert {"SIGN-01", "TOT-01", "MAP-01", "MON-01", "IC-01", "ATI-01", "DUP-02", "MES-01", "DUP-01"} <= reglas
    perfil = json.loads(paquete.read("perfiles/EMP003.json"))
    assert perfil["approved_by"] == "Santiago Enriquez Salguero" and perfil["profile_version"] == 2
    hashes = {h["archivo"]: h["sha256"] for h in leer(paquete, "hashes_sha256.csv")}
    assert hashes == res.input_hashes and all(len(h) == 64 for h in hashes.values())
    for c in res.config.companies.values():                                         # hash real del archivo
        assert hashes[c.file] == hashlib.sha256((DATA / c.file).read_bytes()).hexdigest()
    meta = json.loads(paquete.read("run.json"))
    assert meta["source"]["mode"] == "read_only" and meta["source"]["network"] == "none"
    assert len(leer(paquete, "records.csv")) == len(res.records)


def test_generar_el_paquete_no_toca_los_archivos_fuente():
    antes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in DATA.iterdir() if p.is_file()}
    build_audit_package(run(DATA, profiles_dir=PROFILES), source_dir=DATA)
    assert {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in DATA.iterdir() if p.is_file()} == antes


# ================================================================== nivel de confianza
def test_confianza_cuenta_limpios_y_no_limpios_igual_que_la_clave(res):
    """Registros fuera del consolidado por periodo, segun la clave: oct = dup (2da fila) + sin mapear + signo; nov = moneda Q."""
    fuera = {p: 0 for p in PERIODOS}
    for e in KEY["errores_sembrados"]:
        n = {"moneda_invalida": 1, "cuenta_sin_mapear": 1, "signo_invertido": 1,
             "duplicado_confirmado": 1}.get(e["tipo"], 0)                                # del duplicado solo 1 se excluye
        if n:
            fuera[e["ubicaciones"][0]["period"]] += n
    for p in PERIODOS:
        c = confidence(res, p)
        assert c.bloqueados + c.pendientes + c.duplicados == fuera[p], p
        assert c.limpios + c.bloqueados + c.pendientes + c.duplicados == c.total
        assert c.total == sum(1 for r in res.records if r.period == p and r.status != "TOTAL")
        assert c.pct_limpios == D(c.limpios) / D(c.total)
        assert c.provisional and c.motivos == res.periods[p].provisional_reasons


def test_confianza_niveles(res):
    assert confidence(res, "2026-10").nivel == MEDIA            # 97 % limpio, sin empresas faltantes
    assert confidence(res, "2026-11").nivel == BAJA             # falta EMP006
    assert confidence(res, "2026-12").nivel == MEDIA            # 100 % limpio pero PROVISIONAL (alerta de revision)
    assert ALTA == "ALTA"


# ================================================================== interfaz
CODE_AYUDA = """
import sys
sys.path.insert(0, {root!r})
from nexus.ui import tab_ayuda
tab_ayuda.render()
"""


def test_la_ayuda_trae_glosario_faq_y_limitaciones_sin_chatbot():
    from nexus.limitaciones import LIMITACIONES
    at = AppTest.from_string(CODE_AYUDA.format(root=str(ROOT)), default_timeout=60).run()
    assert not at.exception
    etiquetas = " | ".join(e.label for e in at.expander)
    for termino in ["PROVISIONAL", "Discrepancia intercompañía", "De una cifra a su registro",
                    "Por qué se bloquea un registro", "SUPUESTO", "Sin explicar", "SIMULACIÓN"]:
        assert termino in etiquetas, termino
    assert "Qué NO puede detectar NEXUS" in " ".join(m.value for m in at.markdown)
    for id_, titulo, _ in LIMITACIONES:
        assert f"{id_}. {titulo}" in etiquetas
    assert len(at.chat_input) == 0                                              # sin chatbot


@pytest.fixture()
def app():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120).run()
    assert not at.exception, at.exception
    return at


def test_app_muestra_confianza_y_descarga(app):
    assert any(e.value.startswith("Nivel de confianza del periodo: MEDIA") for e in app.warning)
    assert any(m.label == "Registros limpios" for m in app.metric)
    assert len(app.get("download_button")) == 1


def test_app_conecta_indicadores_variaciones_simulador_y_ayuda(app):
    app.sidebar.radio[0].set_value("2026-11").run()
    assert not app.exception
    texto = " ".join(m.value for m in app.markdown)
    assert "La utilidad neta consolidada baja 80,315.00 USD" in texto                  # Variaciones
    assert any(m.label == "ROIC (mensual)" for m in app.metric)                         # Indicadores
    assert any("SIMULACIÓN" in e.value for e in app.error)                              # Simulador
    assert any(e.label == "PROVISIONAL" for e in app.expander)                          # Ayuda


def test_app_simulador_cambia_con_el_control(app):
    app.slider(key="sim_mxn").set_value(10.0).run()
    assert not app.exception
    tablas = [d.value for d in app.dataframe]
    t = next(t for t in tablas if "SIMULACIÓN" in t.columns and "Ingresos" in set(t["Concepto"]))
    fila = t[t["Concepto"] == "Ingresos"].iloc[0]
    assert fila["Original"] == "1,985,000.00" and fila["SIMULACIÓN"] != fila["Original"]
    assert fila["Diferencia"].startswith("+")
