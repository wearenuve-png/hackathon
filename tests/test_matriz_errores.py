"""Matriz de verificacion de errores (docs/VERIFICACION.md): cada caso con datos MINIMOS.

Cada prueba arma un grupo diminuto (1 o 2 empresas, pocas filas) en una carpeta temporal, con sus perfiles, y lo
pasa por el motor completo. Los valores se calculan a mano en cada prueba."""
import csv
import shutil
from decimal import Decimal

import pytest

from conftest import DATA
from nexus import ingestion
from nexus.pipeline import run
from nexus.profiles import build_profile, save_profile
from nexus.schemas import BLOCKED, EXCLUDED_DUPLICATE, OK, PENDING_MAPPING, Company
from nexus.validation import reverse_adjustment

D = Decimal
HEADER = ["Fecha", "Cuenta", "Monto", "Moneda", "Contraparte", "Referencia"]
PERIODS = ("2026-10", "2026-11", "2026-12")
ACCOUNTS = {"Ventas": "4000", "Costo": "5000", "Alquiler": "6100", "Caja": "1000", "Proveedores": "2000",
            "Capital": "3000"}
RATES = {("GTQ", "2026-10"): "0.125", ("GTQ", "2026-11"): "0.125", ("GTQ", "2026-12"): "0.125",
         ("MXN", "2026-10"): "0.05", ("MXN", "2026-11"): "0.05", ("MXN", "2026-12"): "0.05",
         ("USD", "2026-10"): "1", ("USD", "2026-11"): "1", ("USD", "2026-12"): "1"}
DAY = {"2026-10": "31/10/2026", "2026-11": "30/11/2026", "2026-12": "31/12/2026"}


def row(period, account, amount, currency, cp="", ref="", fecha=None):
    return [fecha or DAY[period], account, amount, currency, cp, ref]


def make(tmp_path, a_rows, b_rows=None, rates=None, periods=PERIODS, a_cur="GTQ", b_cur="MXN", header=HEADER,
         after_profiles=None):
    """Grupo minimo: A01 (moneda a_cur) y opcionalmente B01 (moneda b_cur). Devuelve (resultado, carpeta)."""
    d = tmp_path / "g"
    d.mkdir()
    comps = [("A01", "Empresa A", a_cur, "a01.csv", a_rows)]
    if b_rows is not None:
        comps.append(("B01", "Empresa B", b_cur, "b01.csv", b_rows))
    with open(d / "empresas.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["company_id", "nombre", "pais", "moneda_funcional", "archivo", "alias"])
        for cid, name, cur, fn, _ in comps:
            w.writerow([cid, name, "XX", cur, fn, name])
    rt = RATES if rates is None else rates
    with open(d / "tasas.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["periodo", "moneda", "usd_por_unidad_local"])
        for (cur, p), v in rt.items():
            if p in periods:
                w.writerow([p, cur, v])
    with open(d / "periodos.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["periodo", "tipo"])
        for p in periods:
            w.writerow([p, "real"])
    shutil.copy(DATA / "catalogo_cuentas.csv", d / "catalogo_cuentas.csv")
    with open(d / "equivalencias.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["company_id", "cuenta_local", "account_code"])
        for cid, *_ in comps:
            for name, code in ACCOUNTS.items():
                w.writerow([cid, name, code])
    for cid, name, cur, fn, rows in comps:
        with open(d / fn, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(rows)
    from nexus.config import load_group_config
    cfg = load_group_config(d)
    for cid, name, cur, fn, _ in comps:
        c = Company(cid, name, "XX", cur, fn, [name])
        tables = ingestion.READERS[".csv"](d / fn)
        save_profile(build_profile(c, tables, ACCOUNTS, "csv", approved_by="Tester"), d / "profiles")
    if after_profiles:
        after_profiles(d)
    return run(d, profiles_dir=d / "profiles"), d


def rule(res, rule_id):
    return [f for f in res.findings if f.rule_id == rule_id]


def rec(res, cid, account=None, nth=0):
    rs = [r for r in res.records if r.company_id == cid and (account is None or r.account_local == account)]
    return rs[nth]


# ============================================================ 1. mismo ID dentro de un archivo
def test_caso01_mismo_id_en_un_archivo_se_excluye_con_ajuste_reversible(tmp_path):
    res, _ = make(tmp_path, [row("2026-10", "Ventas", 1000, "GTQ", ref="FAC-1"),
                             row("2026-10", "Ventas", 1000, "GTQ", ref="FAC-1")], periods=("2026-10",))
    a, b = rec(res, "A01", "Ventas", 0), rec(res, "A01", "Ventas", 1)
    assert (a.status, b.status) == (OK, EXCLUDED_DUPLICATE)
    adj = next(x for x in res.adjustments if x.kind == "DUPLICATE_EXCLUSION")
    assert adj.reversible and adj.record_ids == [b.record_id] and adj.reason and adj.rule
    assert res.periods["2026-10"].summary["ingresos"] == D("125")                 # 1,000 GTQ x 0.125, una sola vez
    assert any(e.status == EXCLUDED_DUPLICATE for e in res.periods["2026-10"].excluded)   # visible, no en silencio
    reverse_adjustment(adj, res.records)
    assert b.status == OK and b.amount_original == D("1000")                      # el original nunca se borro


# ============================================================ 2. entre archivos / reenvio del mismo archivo
def test_caso02a_mismo_archivo_reenviado_bajo_otro_nombre_advierte(tmp_path):
    rows = [row("2026-10", "Ventas", 500, "GTQ")]
    res, _ = make(tmp_path, rows, rows, a_cur="GTQ", b_cur="GTQ", periods=("2026-10",))
    f = rule(res, "ARC-01")
    assert len(f) == 1 and "a01.csv" in f[0].message and "b01.csv" in f[0].message and f[0].severity == "WARN"


def test_caso02b_mismo_id_en_dos_empresas_sin_ser_intercompania_advierte(tmp_path):
    res, _ = make(tmp_path, [row("2026-10", "Ventas", 800, "GTQ", ref="FAC-9")],
                  [row("2026-10", "Ventas", 800, "GTQ", ref="FAC-9")], a_cur="GTQ", b_cur="GTQ", periods=("2026-10",))
    f = rule(res, "DUP-03")
    assert len(f) == 1 and "A01" in f[0].message and "B01" in f[0].message
    assert all(r.status == OK for r in res.records)                              # advertir, no excluir


# ============================================================ 3. posible duplicado sin ID
def test_caso03_posible_duplicado_sin_id_solo_se_marca(tmp_path):
    res, _ = make(tmp_path, [row("2026-10", "Alquiler", 250, "GTQ", cp="Proveedor X"),
                             row("2026-10", "Alquiler", 250, "GTQ", cp="Proveedor X")], periods=("2026-10",))
    assert len(rule(res, "DUP-02")) == 1
    assert [r.status for r in res.records] == [OK, OK] and all("POSSIBLE_DUPLICATE" in r.flags for r in res.records)
    assert not [a for a in res.adjustments if a.kind == "DUPLICATE_EXCLUSION"]   # pendiente de confirmacion humana


# ============================================================ 4. archivo declara USD pero el perfil dice GTQ/MXN
@pytest.mark.parametrize("cur", ["GTQ", "MXN"])
def test_caso04_archivo_en_usd_con_perfil_local_se_bloquea_y_va_a_revision(tmp_path, cur):
    res, _ = make(tmp_path, [row(p, "Ventas", 1000, "USD") for p in PERIODS], a_cur=cur)
    rep = res.load_reports["A01"]
    assert rep.status == "REVIEW" and any("declara USD" in r and cur in r for r in rep.reasons)
    assert not [r for r in res.records if r.company_id == "A01"]                  # no se procesa nada
    assert any(f.rule_id == "CARGA-01" for f in res.findings)


def test_caso04b_un_registro_suelto_en_usd_no_bloquea_el_archivo(tmp_path):
    rows = [row("2026-10", "Alquiler", 96000, "GTQ"), row("2026-11", "Alquiler", 96000, "GTQ"),
            row("2026-12", "Alquiler", 96000, "USD")]
    res, _ = make(tmp_path, rows)
    assert res.load_reports["A01"].status == "MATCHED"                           # lo atiende el validador fila a fila


# ============================================================ 5. magnitud sospechosa (x8 o /8)
def test_caso05a_importe_x8_se_marca_como_posible_error_de_moneda_sin_corregir(tmp_path):
    """96,000 marcado USD con historial de 96,000 GTQ (= 12,000 USD): 96,000 / 12,000 = 8 = 1 / 0.125."""
    res, _ = make(tmp_path, [row("2026-10", "Alquiler", 96000, "GTQ"), row("2026-11", "Alquiler", 96000, "GTQ"),
                             row("2026-12", "Alquiler", 96000, "USD")])
    f = rule(res, "ATI-01")
    assert len(f) == 1 and f[0].period == "2026-12" and "error de moneda" in f[0].message
    dic = rec(res, "A01", "Alquiler", 2)
    assert dic.status == OK and dic.amount_usd == D("96000") and "ATYPICAL" in dic.flags       # NO se corrige
    assert "Como GTQ: 12,000.00 USD | como USD: 96,000.00 USD" in f[0].impact
    assert "Efecto en utilidad si fuera GTQ: +84,000.00 USD" in f[0].impact                    # gasto: 96,000 - 12,000
    assert res.periods["2026-12"].summary["gastos_operativos"] == D("96000")                   # consolidado intacto
    assert res.periods["2026-12"].provisional


def test_caso05b_importe_dividido_8_tambien_se_marca(tmp_path):
    """12,000 USD de historial y 12,000 marcado GTQ (= 1,500 USD): 1,500 / 12,000 = 1/8."""
    res, _ = make(tmp_path, [row("2026-10", "Alquiler", 12000, "USD"), row("2026-11", "Alquiler", 12000, "USD"),
                             row("2026-12", "Alquiler", 12000, "GTQ")])
    f = rule(res, "ATI-01")
    assert len(f) == 1 and f[0].period == "2026-12"
    assert "Como USD: 12,000.00 USD | como GTQ: 1,500.00 USD" in f[0].impact
    assert "Efecto en utilidad si fuera USD: -10,500.00 USD" in f[0].impact                    # gasto sube 10,500
    assert rec(res, "A01", "Alquiler", 2).amount_usd == D("1500")


def test_caso05c_limitacion_con_menos_de_tres_periodos_no_se_puede_juzgar(tmp_path):
    res, _ = make(tmp_path, [row("2026-10", "Alquiler", 96000, "GTQ"), row("2026-11", "Alquiler", 96000, "USD")],
                  periods=("2026-10", "2026-11"))
    assert rule(res, "ATI-01") == []                                              # LIMITACION documentada


# ============================================================ 6. moneda desconocida
def test_caso06_moneda_desconocida_bloquea(tmp_path):
    res, _ = make(tmp_path, [row("2026-10", "Ventas", 100, "XYZ"), row("2026-10", "Ventas", 100, "")],
                  periods=("2026-10",))
    xyz, vacia = rec(res, "A01", "Ventas", 0), rec(res, "A01", "Ventas", 1)
    assert xyz.status == vacia.status == BLOCKED and xyz.amount_usd is None and vacia.amount_usd is None
    assert "invalida" in xyz.status_reasons[0] and "faltante" in vacia.status_reasons[0]
    assert len(rule(res, "MON-01")) == 2 and res.periods["2026-10"].summary["ingresos"] == 0


# ============================================================ 7. tipo de cambio faltante o en 0
@pytest.mark.parametrize("valor,motivo", [(None, "Sin tasa"), ("0", "Tasa invalida"), ("", "Sin tasa"),
                                          ("abc", "Sin tasa")])
def test_caso07_tasa_faltante_o_cero_bloquea(tmp_path, valor, motivo):
    rates = dict(RATES)
    if valor is None:
        del rates[("GTQ", "2026-10")]
    else:
        rates[("GTQ", "2026-10")] = valor
    res, _ = make(tmp_path, [row("2026-10", "Ventas", 1000, "GTQ")], rates=rates)
    r = rec(res, "A01", "Ventas")
    assert r.status == BLOCKED and r.amount_usd is None and motivo in r.status_reasons[0]
    assert rule(res, "MON-01") and res.periods["2026-10"].summary["ingresos"] == 0          # nunca 0 USD "valido"


def test_caso07b_moneda_sin_ninguna_tasa_deja_la_carga_en_revision(tmp_path):
    rates = {k: v for k, v in RATES.items() if k[0] != "GTQ"}
    res, _ = make(tmp_path, [row("2026-10", "Ventas", 1000, "GTQ")], rates=rates, periods=("2026-10",))
    assert res.load_reports["A01"].status == "REVIEW" and "sin tasas" in " ".join(res.load_reports["A01"].reasons)
    assert not [r for r in res.records if r.company_id == "A01"]


# ============================================================ 8. columnas renombradas o faltantes
def test_caso08_columnas_renombradas_o_faltantes_bloquean_y_van_a_revision(tmp_path):
    def renombrar(d):
        f = d / "a01.csv"
        f.write_text(f.read_text(encoding="utf-8").replace("Monto", "Importe Total", 1), encoding="utf-8")
    res, _ = make(tmp_path, [row("2026-10", "Ventas", 100, "GTQ")], periods=("2026-10",), after_profiles=renombrar)
    assert res.load_reports["A01"].status == "REVIEW" and "Monto" in " ".join(res.load_reports["A01"].reasons)
    assert not [r for r in res.records if r.company_id == "A01"]


def test_caso08b_columna_faltante_bloquea(tmp_path):
    def quitar(d):
        f = d / "a01.csv"
        lines = [ln.split(",") for ln in f.read_text(encoding="utf-8").splitlines()]
        f.write_text("\n".join(",".join(c for i, c in enumerate(ln) if i != 3) for ln in lines) + "\n",
                     encoding="utf-8")                                                       # quita 'Moneda'
    res, _ = make(tmp_path, [row("2026-10", "Ventas", 100, "GTQ")], periods=("2026-10",), after_profiles=quitar)
    assert res.load_reports["A01"].status == "REVIEW" and "Moneda" in " ".join(res.load_reports["A01"].reasons)


# ============================================================ 9. signo, fecha, cuenta, texto
def test_caso09a_signo_invertido(tmp_path):
    res, _ = make(tmp_path, [row("2026-10", "Costo", -500, "GTQ")], periods=("2026-10",))
    r = rec(res, "A01", "Costo")
    assert r.status == BLOCKED and "Signo invertido" in r.status_reasons[0] and rule(res, "SIGN-01")


def test_caso09b_fecha_fuera_de_periodo_y_fecha_invalida(tmp_path):
    res, _ = make(tmp_path, [row("2026-10", "Ventas", 100, "GTQ", fecha="15/03/2027"),
                             row("2026-10", "Ventas", 100, "GTQ", fecha="31/13/2026"),
                             row("2026-10", "Ventas", 100, "GTQ")], periods=("2026-10",))
    fuera, invalida, ok = (rec(res, "A01", "Ventas", i) for i in range(3))
    assert fuera.status == BLOCKED and "fuera del calendario" in fuera.status_reasons[0] and rule(res, "FEC-01")
    assert invalida.status == BLOCKED and "Periodo invalido" in invalida.status_reasons[0]
    assert ok.status == OK and res.periods["2026-10"].summary["ingresos"] == D("12.5")       # solo entra 100 x 0.125


def test_caso09c_cuenta_sin_mapear(tmp_path):
    res, _ = make(tmp_path, [row("2026-10", "Cuenta rara", 100, "GTQ")], periods=("2026-10",))
    r = rec(res, "A01")
    assert r.status == PENDING_MAPPING and r.account_code is None and rule(res, "MAP-01")
    assert res.periods["2026-10"].summary["utilidad_neta"] == 0


def test_caso09d_texto_en_campo_numerico(tmp_path):
    res, _ = make(tmp_path, [row("2026-10", "Ventas", "abc", "GTQ"), row("2026-10", "Ventas", "", "GTQ")],
                  periods=("2026-10",))
    txt, vacio = rec(res, "A01", "Ventas", 0), rec(res, "A01", "Ventas", 1)
    assert txt.status == vacio.status == BLOCKED and txt.amount_original is None
    assert "no numerico" in txt.status_reasons[0] and "vacio" in vacio.status_reasons[0]


# ============================================================ 10. diferencia intercompania
def test_caso10_diferencia_intercompania_queda_abierta_y_no_se_elimina(tmp_path):
    """A (GTQ) vende 160,000 GTQ = 20,000 USD; B (MXN) compra 360,000 MXN = 18,000 USD: diferencia 2,000."""
    res, _ = make(tmp_path, [row("2026-10", "Ventas", 160000, "GTQ", cp="Empresa B", ref="IC-1")],
                  [row("2026-10", "Costo", 360000, "MXN", cp="Empresa A", ref="IC-1")], periods=("2026-10",))
    m = res.matches[0]
    assert m.status == "DISCREPANCY" and m.seller_usd == D("20000") and m.buyer_usd == D("18000")
    assert m.difference_usd == D("2000")
    assert not [a for a in res.adjustments if a.kind == "IC_ELIMINATION"]          # nunca se elimina sola
    s = res.periods["2026-10"].summary
    assert s["ingresos"] == D("20000") and s["costo_ventas"] == D("18000")         # ambos lados siguen en el consolidado
    assert res.periods["2026-10"].provisional and rule(res, "IC-01")


# ============================================================ 11. balance descuadrado
def test_caso11_balance_descuadrado_alerta(tmp_path):
    """Activo 1,000 GTQ vs pasivo 300 + patrimonio 600 = 900: diferencia 100 GTQ = 12.50 USD."""
    res, _ = make(tmp_path, [row("2026-10", "Caja", 1000, "GTQ"), row("2026-10", "Proveedores", 300, "GTQ"),
                             row("2026-10", "Capital", 600, "GTQ")], periods=("2026-10",))
    f = rule(res, "BAL-01")
    assert len(f) == 1 and "12.50" in f[0].message and f[0].severity == "WARN"
    assert res.periods["2026-10"].provisional


def test_caso11b_balance_cuadrado_no_alerta(tmp_path):
    res, _ = make(tmp_path, [row("2026-10", "Caja", 1000, "GTQ"), row("2026-10", "Proveedores", 300, "GTQ"),
                             row("2026-10", "Capital", 700, "GTQ")], periods=("2026-10",))
    assert rule(res, "BAL-01") == [] and res.periods["2026-10"].summary["activo_menos_pasivo_y_patrimonio"] == 0


# ============================================================ la documentacion no promete de mas
def test_el_documento_de_verificacion_lista_todos_los_casos_y_limitaciones():
    from pathlib import Path
    from nexus.limitaciones import LIMITACIONES
    doc = (Path(__file__).resolve().parent.parent / "docs" / "VERIFICACION.md").read_text(encoding="utf-8")
    for n in ["1", "2a", "2b", "3", "4", "5", "6", "7", "8", "9a", "9b", "9c", "9d", "10", "11"]:
        assert f"| {n} |" in doc, f"Falta el caso {n} en la matriz"
    for id_, titulo, _ in LIMITACIONES:
        assert f"| {id_} | {titulo} |" in doc
    # cada prueba citada en la matriz existe
    import re
    src = Path(__file__).read_text(encoding="utf-8")
    for nombre in re.findall(r"`(caso\d+[a-z]?)`", doc):
        assert re.search(rf"def test_{nombre}", src), f"La matriz cita {nombre} pero no existe esa prueba"
