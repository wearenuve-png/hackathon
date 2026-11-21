"""Demo de respaldo: corre TODO el flujo sin interfaz, imprime cada paso con sus cifras clave y
exporta la evidencia. Sigue el mismo recorrido que docs/GUION_DEMO.md. Datos SINTETICOS (Grupo Ferrex).

    .venv/bin/python scripts/demo_respaldo.py [--datos data/synthetic] [--perfiles profiles] [--salida data/output]

Solo lee los archivos (solo lectura), sin red. Termina en segundos.
"""
import argparse
import sys
import time
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from nexus import audit, variance  # noqa: E402
from nexus.variance import CAUSE_NAMES, SIN, sfmt  # noqa: E402
from nexus.consolidation import trace  # noqa: E402
from nexus.metrics import compute_indicators  # noqa: E402
from nexus.pipeline import run  # noqa: E402

PERIODO = "2026-10"


def m(d, plus=False):
    if d is None:
        return "n/c"
    s = f"{d.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):,.2f}"
    return ("+" + s) if plus and d > 0 else s


def paso(n, titulo, out):
    out(f"\n{'=' * 78}\nPASO {n}: {titulo}\n{'=' * 78}")


def run_demo(datos, perfiles, salida, out=print) -> dict:
    """Ejecuta el flujo y devuelve las cifras clave (para la prueba contra answer_key.json)."""
    t0 = time.time()
    datos, salida = Path(datos), Path(salida)
    res = run(datos, profiles_dir=perfiles)
    pr = res.periods[PERIODO]
    cfg = res.config
    k = {"periodo": PERIODO}

    paso(1, "El problema", out)
    out("6 empresas, 3 monedas y 6 formatos distintos. Hoy se consolidan a mano: semanas de trabajo, ventas "
        "entre empresas contadas doble y errores que nadie ve.\nNEXUS lo hace en segundos, sin captura manual y "
        "con cada cifra rastreable. DATOS SINTETICOS (Grupo Ferrex).")

    paso(2, "Los 6 formatos, cada uno contra su perfil (fuente: carpeta del servidor, solo lectura)", out)
    out(f"Fuente: carpeta del servidor, solo lectura: {datos}\n")
    out(f"{'Empresa':<9}{'Formato':<9}{'Archivo':<34}{'Perfil':<8}{'Aprobado por':<28}{'Ultima carga':<14}{'Regs':>5}")
    for cid, c in cfg.companies.items():
        rep, p = res.load_reports[cid], cfg.profiles[cid]
        out(f"{cid:<9}{p.source.type.upper():<9}{c.file:<34}v{p.profile_version:<7}{(p.approved_by or 'PENDIENTE'):<28}"
            f"{rep.status:<14}{rep.n_records:>5}")
    ver = audit.verify_hashes(res.input_hashes, [datos, perfiles])
    out("\nIntegridad (SHA-256 registrado al leer vs. ahora):")
    for f, v in list(ver.items())[:6]:
        out(f"  {f:<34}{v['status']:<8}{v['registered'][:24]}...")
    out(f"  ... {len(ver)} archivos en total, {sum(v['status'] == 'OK' for v in ver.values())} sin cambios")
    k["archivos_ok"] = sum(v["status"] == "OK" for v in ver.values())
    k["cargas_coinciden"] = sum(r.status == "MATCHED" for r in res.load_reports.values())

    paso(3, f"Un error sembrado detectado y bloqueado ({PERIODO}): rango de impacto y etiqueta PROVISIONAL", out)
    out(f"Periodo {PERIODO}: {'PROVISIONAL' if pr.provisional else 'DEFINITIVO'}")
    for why in pr.provisional_reasons:
        out(f"  * {why}")
    out("\nFuera del consolidado (nada se excluye en silencio):")
    for e in pr.excluded:
        out(f"  - {e.record_id} [{e.status}] {m(e.amount_original)} {e.currency} = {m(e.amount_usd)} USD: "
            f"{'; '.join(e.reasons)}")
    out("\nImpacto en utilidad neta (ninguna cifra se modifica):")
    out(f"  {'Registro':<52}{'Excluido':>10}{'Como viene':>13}{'Corregido':>13}")
    k["bloqueados"] = []
    for i in pr.impact_ranges:
        out(f"  {i.record_id[-50:]:<52}{m(i.utility_excluded):>10}{m(i.utility_as_is, True):>13}"
            f"{m(i.utility_corrected, True):>13}")
        out(f"      {i.note}")
        k["bloqueados"].append({"record_id": i.record_id, "as_is": i.utility_as_is, "corrected": i.utility_corrected})
    lo, hi = pr.utility_range
    out(f"\nUtilidad neta mostrada: {m(pr.summary['utilidad_neta'])} USD | rango posible: {m(lo)} a {m(hi)} USD")
    k["rango_utilidad"] = (lo, hi)
    pr11 = res.periods["2026-11"]
    for e in pr11.excluded:
        if any("Moneda" in r for r in e.reasons):
            out(f"\nEn 2026-11, moneda invalida: {e.record_id} -> {'; '.join(e.reasons)} (USD {m(e.amount_usd)}: "
                f"no se asume la moneda)")

    paso(4, f"Consolidado de {PERIODO} en USD vs. la suma ingenua", out)
    out(f"{'Concepto':<22}{'Suma ingenua':>16}{'Eliminaciones':>16}{'Consolidado':>16}")
    for lbl, key in (("Ingresos", "ingresos"), ("Costo de ventas", "costo_ventas"),
                     ("Gastos operativos", "gastos_operativos"), ("Utilidad neta", "utilidad_neta")):
        out(f"{lbl:<22}{m(pr.naive_summary[key]):>16}{m(pr.summary[key] - pr.naive_summary[key], True):>16}"
            f"{m(pr.summary[key]):>16}")
    out(f"\nLa suma ingenua cuenta doble lo que las empresas se venden entre si: "
        f"{m(pr.naive_summary['ingresos'] - pr.summary['ingresos'])} USD de ingresos. La utilidad no cambia.")
    out(f"Balance: Activo - (Pasivo + Patrimonio) = {m(pr.summary['activo_menos_pasivo_y_patrimonio'])}")
    k["ingresos"], k["utilidad_neta"] = pr.summary["ingresos"], pr.summary["utilidad_neta"]
    k["ingresos_ingenuo"], k["utilidad_ingenua"] = pr.naive_summary["ingresos"], pr.naive_summary["utilidad_neta"]
    k["eliminaciones_conciliadas"] = sum(1 for x in res.matches if x.period == PERIODO and x.status == "RECONCILED")

    paso(5, "La discrepancia intercompania que NO se elimina", out)
    k["discrepancias"] = []
    unidas = {}
    for x in [x for x in res.matches if x.status == "DISCREPANCY"]:
        k["discrepancias"].append({"reference": x.reference, "period": x.period, "difference": x.difference_usd})
        unidas.setdefault((x.period, x.seller_id, x.buyer_id, x.reference), []).append(x)
    for (per, vend, comp, ref), xs in unidas.items():
        x = xs[0]
        afecta = " y ".join("la operacion (la venta)" if y.statement == "ER" else
                            "el saldo (cuenta por cobrar y por pagar)" for y in sorted(xs, key=lambda y: y.statement != "ER"))
        out(f"  {per} {vend} -> {comp} ref {ref}: {vend} {m(x.seller_usd)} vs {comp} {m(x.buyer_usd)} USD = "
            f"diferencia {m(x.difference_usd)} USD. No se elimina; se abre para revision.")
        out(f"  Se muestra una sola vez: la misma diferencia afecta {afecta}.")

    paso(6, "De una cifra a su registro original: Ingresos por ventas (cuenta 4000) -> archivo, hoja y fila", out)
    t = trace(PERIODO, "4000", res)
    out(f"Ingresos por ventas (cuenta {t['account_code']}): {m(t['gross_usd'])} antes de eliminar, "
        f"{m(t['amount_usd'])} despues ({len(t['records'])} registros fuente, {len(t['adjustments'])} ajustes)")
    otras = {c: ln.amount_usd for c, ln in pr.lines.items()
             if cfg.catalog[c].cls == "ingreso" and c != "4000" and ln.amount_usd}
    out(f"Nota: esta cifra ({m(t['amount_usd'])} USD) es solo la cuenta 4000. Difiere del total de ingresos del "
        f"consolidado ({m(pr.summary['ingresos'])} USD) porque ese total incluye otras cuentas de ingresos: "
        + ", ".join(f"{c} {cfg.catalog[c].name} ({m(v)} USD)" for c, v in otras.items()) + ".")
    out(f"  {'Empresa':<8}{'Archivo':<30}{'Hoja':<18}{'Fila':>5}{'Original':>16}{'Mon':>5}{'Tasa':>7}{'USD':>14}")
    for x in sorted(t["records"], key=lambda r: -r["amount_usd"])[:4]:
        out(f"  {x['company_id']:<8}{x['file']:<30}{(x['sheet'] or '-'):<18}{x['row']:>5}{m(x['amount_original']):>16}"
            f"{x['currency']:>5}{str(x['fx_rate']):>7}{m(x['amount_usd']):>14}")
    a = t["adjustments"][0]
    out(f"  Ajuste: {a['adjustment_id']} {a['kind']} {m(a['amount_usd'], True)} USD - {a['reason']}")
    k["trace_registros"] = len(t["records"])
    k["trace_total"] = sum(x["amount_usd"] for x in t["records"]) + sum(x["amount_usd"] for x in t["adjustments"])
    k["trace_final"] = t["amount_usd"]

    paso(7, "Indicadores ROIC, ROCE y EVA (MENSUALES, con supuestos visibles, datos sinteticos)", out)
    ind = compute_indicators(res, PERIODO)
    out(f"{'Entrada':<34}{'Valor':>16}  Origen")
    for i in ind.inputs:
        v = f"{i.value:,.4f}".rstrip("0").rstrip(".") if i.name in ("WACC (anual)", "Tasa de impuesto") else m(i.value)
        out(f"{i.name:<34}{v:>16}  {i.source}")
    out(f"\nNOPAT  = EBIT x (1 - tasa)                 = {m(ind.nopat)}")
    out(f"ROIC   = NOPAT / capital invertido         = {ind.roic:.2%} del mes")
    out(f"ROCE   = EBIT / capital empleado           = {ind.roce:.2%} del mes")
    out(f"EVA    = NOPAT - (WACC/12) x capital       = {m(ind.eva)} USD del mes")
    out("WACC, tasa de impuesto y definicion de capital son SUPUESTO del equipo, no datos del reto.")
    out(f"(*) Nota al pie: anualizados serian ROIC {ind.roic_annualized:.2%} y ROCE {ind.roce_annualized:.2%}; "
        f"no son representativos por ser datos sinteticos.")
    k["ind"] = {"nopat": ind.nopat, "roic": ind.roic, "roce": ind.roce, "eva": ind.eva}

    paso(8, "Una variacion explicada con registros concretos (2026-10 -> 2026-11)", out)
    rep = variance.compare(variance.view(res, PERIODO), variance.view(res, "2026-11"))
    tot = rep.total
    out(tot.phrase)
    out(f"\n  {'Causa':<62}{'USD':>14}")
    for kk, x in tot.causes.items():
        if x != 0 or kk == SIN:
            out(f"  {CAUSE_NAMES[kk]:<62}{sfmt(x):>14}")
    out(f"  {'TOTAL (suma de causas + sin explicar)':<62}{sfmt(tot.causes_sum):>14}")
    out(f"  Etiquetas: {', '.join(tot.tags)}. Convencion: {rep.convention}")
    sin_cell = next((v for v in rep.cells.values() if v.causes[SIN] != 0), None)
    if sin_cell:
        out(f"\nLo que los datos NO prueban: {sin_cell.label}: sin explicar {sfmt(sin_cell.causes[SIN])} USD "
            f"en la cuenta (como es un gasto, pesa {sfmt(tot.causes[SIN])} en la utilidad neta)")
        for n in sin_cell.notes:
            out(f"  - {n}")
        cid, code = sin_cell.key.split("|")
        t = next(t for t in rep.by_account[code].trace if t.company_id == cid and t.status == "BLOCKED")
        out(f"  Trazabilidad: {t.file}, hoja {t.sheet or '-'}, fila {t.row}: {t.local:,.2f} {t.currency}, "
            f"{t.status} - {t.rule}")
    k["variacion"] = {"total": tot.total, "causas": dict(tot.causes), "causas_suma": tot.causes_sum,
                      "sin_explicar_celdas": [v.key for v in rep.cells.values() if v.causes[SIN] != 0]}
    k["explicador_pendiente"] = False

    ruta = audit.write_run(res, salida, source_dir=datos)
    out(f"\nEvidencia exportada en: {ruta}  (run.json, records.csv)")
    k["evidencia"], k["segundos"] = ruta, time.time() - t0
    out(f"Tiempo total: {k['segundos']:.2f} s")
    return k


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--datos", default=str(ROOT / "data" / "synthetic"))
    ap.add_argument("--perfiles", default=str(ROOT / "profiles"))
    ap.add_argument("--salida", default=str(ROOT / "data" / "output"))
    a = ap.parse_args()
    run_demo(a.datos, a.perfiles, a.salida)


if __name__ == "__main__":
    main()
