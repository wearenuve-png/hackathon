"""Las cifras que imprime scripts/demo_respaldo.py coinciden con tests/fixtures/answer_key.json
(calculadas aqui de forma independiente del motor, con Decimal)."""
import subprocess
import sys
import time
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pytest

from conftest import DATA, KEY, ROOT

D = Decimal
sys.path.insert(0, str(ROOT / "scripts"))
import demo_respaldo  # noqa: E402

PROFILES = ROOT / "profiles"


def q2(d):
    return D(d).quantize(D("0.01"), rounding=ROUND_HALF_UP)


def fmt(s):
    return f"{q2(s):,.2f}"


def rate(period, cur):
    import csv
    with open(DATA / "tasas.csv", encoding="utf-8") as f:
        return next(D(r["usd_por_unidad_local"]) for r in csv.DictReader(f)
                    if r["periodo"] == period and r["moneda"] == cur)


@pytest.fixture(scope="module")
def demo(tmp_path_factory):
    lines = []
    out = tmp_path_factory.mktemp("salida")
    k = demo_respaldo.run_demo(DATA, PROFILES, out, out=lines.append)
    return k, "\n".join(lines), out


def test_consolidado_de_octubre_igual_a_la_clave(demo):
    k, _, _ = demo
    exp = KEY["consolidado_esperado_usd"]["2026-10"]["resumen"]
    naive = KEY["suma_ingenua_sin_eliminar_usd"]["2026-10"]
    assert q2(k["ingresos"]) == D(exp["ingresos"]) and q2(k["utilidad_neta"]) == D(exp["utilidad_neta"])
    assert q2(k["ingresos_ingenuo"]) == D(naive["ingresos"]) and q2(k["utilidad_ingenua"]) == D(naive["utilidad_neta"])


def test_las_cifras_del_guion_estan_en_la_clave(demo):
    k, _, _ = demo
    assert (fmt(k["ingresos"]), fmt(k["utilidad_neta"]), fmt(k["ingresos_ingenuo"])) == \
        ("1,985,000.00", "359,125.00", "2,078,000.00")


def test_eliminaciones_y_discrepancias_igual_a_la_clave(demo):
    k, _, _ = demo
    assert k["eliminaciones_conciliadas"] == sum(1 for e in KEY["eliminaciones_esperadas"] if e["period"] == "2026-10")
    got = {(d["reference"], d["period"], q2(d["difference"])) for d in k["discrepancias"]}
    assert got == {(d["reference"], d["period"], D(d["difference_usd"])) for d in KEY["discrepancias_esperadas"]}
    assert D(KEY["discrepancias_esperadas"][0]["difference_usd"]) == D("2000.00")


def test_rango_de_impacto_igual_al_calculo_independiente(demo):
    k, _, _ = demo
    err = {e["tipo"]: e for e in KEY["errores_sembrados"]}
    sign = err["signo_invertido"]["ubicaciones"][0]
    usd_sign = D(sign["amount_local"]) * rate(sign["period"], sign["currency_written"])
    pend = err["cuenta_sin_mapear"]["ubicaciones"][0]
    usd_pend = abs(D(pend["amount_local"]) * rate(pend["period"], pend["currency_written"]))
    sg = next(b for b in k["bloqueados"] if b["record_id"].endswith(f"|{sign['row']}"))
    assert sg["as_is"] == -usd_sign and sg["corrected"] == usd_sign             # gasto: efecto en utilidad
    base = D(KEY["consolidado_esperado_usd"]["2026-10"]["resumen"]["utilidad_neta"])
    lo, hi = k["rango_utilidad"]
    assert q2(lo) == base - abs(usd_sign) - usd_pend and q2(hi) == base + abs(usd_sign) + usd_pend


def test_trazabilidad_suma_igual_a_la_cifra(demo):
    k, _, _ = demo
    assert k["trace_registros"] > 0 and k["trace_total"] == k["trace_final"]
    por_cuenta = KEY["consolidado_esperado_usd"]["2026-10"]["por_cuenta"]["4000"]
    assert q2(k["trace_final"]) == D(por_cuenta)


def test_indicadores_igual_al_calculo_independiente(demo):
    k, _, _ = demo
    kk = KEY["consolidado_esperado_usd"]["2026-10"]
    cta, rs = {c: D(v) for c, v in kk["por_cuenta"].items()}, {c: D(v) for c, v in kk["resumen"].items()}
    nopat = rs["ebit"] * D("0.75")
    ci = cta["2500"] + rs["patrimonio"] - cta["1000"]
    ce = rs["activo_total"] - (cta["2000"] + cta["2100"])
    assert abs(k["ind"]["nopat"] - nopat) <= D("0.01")
    assert abs(k["ind"]["roic"] - nopat / ci) < D("0.000001") and abs(k["ind"]["roce"] - rs["ebit"] / ce) < D("0.000001")
    assert abs(k["ind"]["eva"] - (nopat - D("0.08") / 12 * ci)) <= D("0.05")


def test_estado_de_carga_y_hashes(demo):
    k, _, _ = demo
    assert k["cargas_coinciden"] == 6
    config_csv = ["empresas", "tasas", "periodos", "catalogo_cuentas", "equivalencias"]
    assert all((DATA / f"{c}.csv").exists() for c in config_csv)
    assert k["archivos_ok"] == 6 + len(config_csv) + len(list(PROFILES.glob("*.json")))   # empresas + tablas + perfiles


def test_el_paso_8_explica_la_variacion_y_suma_exacto(demo):
    k, txt, _ = demo
    v = k["variacion"]
    a, b = KEY["consolidado_esperado_usd"]["2026-10"]["resumen"], KEY["consolidado_esperado_usd"]["2026-11"]["resumen"]
    assert q2(v["total"]) == D(b["utilidad_neta"]) - D(a["utilidad_neta"]) == D("-80315.00")
    assert v["causas_suma"] == v["total"]                                       # las causas suman EXACTO
    assert k["explicador_pendiente"] is False and "PENDIENTE" not in txt.split("PASO 8:")[1]
    p8 = txt.split("PASO 8:")[1]
    assert "-80,315.00" in p8 and "Sin explicar" in p8 and "'Q'" in p8 and "distribuidora_central_gt.csv" in p8
    assert v["sin_explicar_celdas"] == ["EMP002|6000"]


def test_el_script_corre_solo_en_menos_de_un_minuto_y_exporta_evidencia(tmp_path):
    t0 = time.time()
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "demo_respaldo.py"), "--salida", str(tmp_path)],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    assert time.time() - t0 < 60
    for n in range(1, 9):
        assert f"PASO {n}:" in r.stdout
    for cifra in ("1,985,000.00", "359,125.00", "2,078,000.00", "2,000.00", "SUPUESTO", "PROVISIONAL",
                  "carpeta del servidor, solo lectura"):
        assert cifra in r.stdout, cifra
    runs = list(Path(tmp_path).glob("run-*"))
    assert len(runs) == 1 and (runs[0] / "run.json").exists() and (runs[0] / "records.csv").exists()


# ---------------------------------------------------------------- ajustes de redaccion del guion
def test_indicadores_en_el_cuerpo_son_solo_mensuales(demo):
    _, txt, _ = demo
    cuerpo = txt.split("PASO 7:")[1].split("PASO 8:")[0]
    lineas = [ln for ln in cuerpo.splitlines() if ln.startswith(("ROIC", "ROCE", "EVA"))]
    assert len(lineas) == 3 and all("del mes" in ln for ln in lineas)
    assert not any("anualiz" in ln for ln in lineas)                         # nada anualizado en el cuerpo
    pie = [ln for ln in cuerpo.splitlines() if "anualizado" in ln]
    assert len(pie) == 1 and pie[0].startswith("(*) Nota al pie") and "no son representativos" in pie[0]


def test_paso_6_aclara_por_que_difiere_del_total_de_ingresos(demo):
    k, txt, _ = demo
    p6 = txt.split("PASO 6:")[1].split("PASO 7:")[0]
    assert "Ingresos por ventas (cuenta 4000)" in p6
    cuenta = fmt(KEY["consolidado_esperado_usd"]["2026-10"]["por_cuenta"]["4000"])
    total = fmt(KEY["consolidado_esperado_usd"]["2026-10"]["resumen"]["ingresos"])
    otra = fmt(KEY["consolidado_esperado_usd"]["2026-10"]["por_cuenta"]["4100"])
    nota = next(ln for ln in p6.splitlines() if ln.startswith("Nota:"))
    assert cuenta in nota and total in nota and "otras cuentas de ingresos" in nota and otra in nota
    assert D(total.replace(",", "")) - D(cuenta.replace(",", "")) == D(otra.replace(",", ""))   # 1,985,000 = 1,865,000 + 120,000


def test_paso_5_explica_por_que_hay_dos_filas(demo):
    _, txt, _ = demo
    p5 = txt.split("PASO 5:")[1].split("PASO 6:")[0]
    assert "una sola vez" in p5 and "operacion (la venta)" in p5 and "saldo (cuenta por cobrar y por pagar)" in p5
    assert "dos filas" not in p5
    assert sum(1 for ln in p5.splitlines() if "DC-IC-2611-MX" in ln) == 1                    # la discrepancia, una sola vez
    assert len(KEY["discrepancias_esperadas"]) == 2                                          # son 2 coincidencias en la clave


def test_el_guion_refleja_los_ajustes():
    g = (ROOT / "docs" / "GUION_DEMO.md").read_text(encoding="utf-8")
    paso7 = g.split("### 7.")[1].split("### 8.")[0]
    cuerpo7 = paso7.split("*Nota al pie")[0]
    assert "anualiz" not in cuerpo7 and "mensuales" in cuerpo7
    assert "no\nson representativas por ser datos sintéticos" in paso7
    paso6 = g.split("### 6.")[1].split("### 7.")[0]
    assert "Ingresos por ventas (cuenta 4000)" in paso6 and "1,985,000" in paso6 and "4100" in paso6
    paso5 = g.split("### 5.")[1].split("### 6.")[0]
    assert "una sola diferencia" in paso5 and "cuenta por\ncobrar y por pagar" in paso5
