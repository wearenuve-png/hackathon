"""Ejecuta FinaCore de punta a punta sin interfaz y exporta la evidencia.

    .venv/bin/python scripts/run_pipeline.py [carpeta_datos] [--periodo 2026-10]
"""
import argparse
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from nexus import audit  # noqa: E402
from nexus.pipeline import run  # noqa: E402


def m(d):
    return f"{d.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):>16,.2f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("datos", nargs="?", default="data/synthetic")
    ap.add_argument("--periodo", action="append")
    ap.add_argument("--salida", default="data/output")
    ap.add_argument("--historial", action="store_true",
                    help="advertir si un archivo o ID ya fue cargado en una ejecucion anterior guardada en --salida")
    a = ap.parse_args()
    r = run(a.datos, history_dir=a.salida if a.historial else None)
    for p, pr in r.periods.items():
        if a.periodo and p not in a.periodo:
            continue
        estado = "PROVISIONAL" if pr.provisional else "DEFINITIVO"
        print(f"\n=== {p} ({pr.kind}) - {estado} ===")
        for why in pr.provisional_reasons:
            print(f"  * {why}")
        print(f"\n  {'Concepto':<24}{'Suma ingenua':>16}{'Consolidado':>16}")
        for k in ("ingresos", "costo_ventas", "gastos_operativos", "ebit", "gastos_financieros", "impuestos",
                  "utilidad_neta", "activo_total", "pasivo_total", "patrimonio"):
            print(f"  {k:<24}{m(pr.naive_summary[k])}{m(pr.summary[k])}")
        if pr.excluded:
            print("\n  Quedo FUERA del consolidado:")
            for e in pr.excluded:
                usd = m(e.amount_usd).strip() + " USD" if e.amount_usd is not None else "USD no calculable"
                print(f"   - {e.record_id}: {e.amount_original} {e.currency} ({usd}) [{e.status}] {'; '.join(e.reasons)}")
            for s, v in pr.excluded_usd_by_status.items():
                print(f"     Total {s}: {m(v).strip()} USD")
            if pr.excluded_not_convertible:
                print(f"     + {pr.excluded_not_convertible} registro(s) sin conversion posible (ver arriba)")
        if pr.impact_ranges:
            print("\n  Impacto en utilidad neta de lo que quedo fuera (PROVISIONAL, ninguna cifra se modifica):")
            print(f"   {'Registro':<46}{'Excluido':>12}{'Como viene':>14}{'Corregido':>14}")
            for i in pr.impact_ranges:
                f = lambda v: "n/c" if v is None else m(v).strip()
                print(f"   {i.record_id[-44:]:<46}{f(i.utility_excluded):>12}{f(i.utility_as_is):>14}{f(i.utility_corrected):>14}")
                print(f"      {i.note}")
            lo, hi = pr.utility_range
            print(f"   Utilidad neta mostrada: {m(pr.summary['utilidad_neta']).strip()} USD | rango posible: "
                  f"{m(lo).strip()} a {m(hi).strip()} USD")
        for x in [x for x in r.findings if x.period == p and x.rule_id in ("ATI-01", "DUP-02", "TOT-01")]:
            print(f"   [{x.rule_id}] {x.message}")
            if x.impact:
                print(f"       impacto: {x.impact}")
        disc = [x for x in r.matches if x.period == p and x.status != "RECONCILED"]
        elim = [x for x in r.matches if x.period == p and x.status == "RECONCILED"]
        print(f"\n  Intercompania: {len(elim)} conciliadas y eliminadas, {len(disc)} abiertas")
        for x in disc:
            print(f"   ! {x.status} {x.seller_id}->{x.buyer_id} ref {x.reference} ({x.statement}): "
                  f"{m(x.seller_usd).strip()} vs {m(x.buyer_usd).strip()} USD, diferencia {m(x.difference_usd).strip()}")
    print(f"\nEvidencia exportada en: {audit.write_run(r, a.salida, source_dir=a.datos)}")


if __name__ == "__main__":
    main()
