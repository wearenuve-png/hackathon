"""Consolidado por periodo y cuenta, con trazabilidad y exclusiones visibles.

- Suma solo registros OK convertidos a USD; las filas de total nunca se suman.
- Aplica las eliminaciones intercompania (ajustes IC_ELIMINATION).
- Todo lo que queda fuera (bloqueado, pendiente, duplicado excluido) se lista con importe y motivo.
- Un periodo es PROVISIONAL si le faltan empresas, tiene registros bloqueados/pendientes,
  discrepancias intercompania abiertas o alertas pendientes.
"""
from collections import defaultdict
from decimal import Decimal
from typing import Dict, List

from .schemas import (BLOCK, BLOCKED, EXCLUDED_DUPLICATE, OK, PENDING_MAPPING, TOTAL, WARN, Adjustment,
                      ConsolidatedLine, ExcludedItem, Finding, GroupConfig, ICMatch, PeriodResult, Record)

SUMMARY_CLASSES = {"ingresos": "ingreso", "costo_ventas": "costo", "gastos_operativos": "gasto_operativo",
                   "gastos_financieros": "gasto_financiero", "impuestos": "impuesto",
                   "activo_total": "activo", "pasivo_total": "pasivo", "patrimonio": "patrimonio"}
UNRESOLVED = {BLOCKED, PENDING_MAPPING}


def summarize(amounts: Dict[str, Decimal], cfg: GroupConfig) -> Dict[str, Decimal]:
    s = {k: sum((v for c, v in amounts.items() if cfg.catalog[c].cls == cls), Decimal(0))
         for k, cls in SUMMARY_CLASSES.items()}
    s["ebit"] = s["ingresos"] - s["costo_ventas"] - s["gastos_operativos"]
    s["utilidad_neta"] = s["ebit"] - s["gastos_financieros"] - s["impuestos"]
    s["activo_menos_pasivo_y_patrimonio"] = s["activo_total"] - s["pasivo_total"] - s["patrimonio"]
    return s


def consolidate(records: List[Record], adjustments: List[Adjustment], matches: List[ICMatch],
                findings: List[Finding], cfg: GroupConfig) -> Dict[str, PeriodResult]:
    periods = sorted(set(cfg.periods) | {r.period for r in records if r.period})
    codes = [c for c, a in cfg.catalog.items() if a.cls != "total"]
    out = {}
    for p in periods:
        lines = {c: ConsolidatedLine(p, c, Decimal(0), Decimal(0)) for c in codes}
        for r in records:
            if r.period == p and r.status == OK and r.amount_usd is not None and r.account_code in lines:
                ln = lines[r.account_code]
                ln.gross_usd += r.amount_usd
                ln.record_ids.append(r.record_id)
        for c, ln in lines.items():
            ln.amount_usd = ln.gross_usd
        for a in adjustments:
            if a.period == p and a.kind == "IC_ELIMINATION" and a.account_code in lines:
                lines[a.account_code].amount_usd += a.amount_usd
                lines[a.account_code].adjustment_ids.append(a.adjustment_id)

        excluded = [ExcludedItem(r.record_id, r.company_id, r.period, r.status, list(r.status_reasons),
                                 r.amount_original, r.currency, r.amount_usd)
                    for r in records if r.period == p and r.status not in (OK, TOTAL)]
        by_status = defaultdict(Decimal)
        for e in excluded:
            if e.amount_usd is not None:
                by_status[e.status] += e.amount_usd
        not_conv = sum(1 for e in excluded if e.amount_usd is None)

        present = {r.company_id for r in records if r.period == p}
        missing = sorted(set(cfg.companies) - present)

        reasons = []
        if missing:
            reasons.append(f"Faltan datos de: {', '.join(missing)}")
        n_unres = sum(1 for e in excluded if e.status in UNRESOLVED)
        if n_unres:
            reasons.append(f"{n_unres} registro(s) bloqueado(s) o pendiente(s) de confirmacion fuera del consolidado")
        open_ic = [m for m in matches if m.period == p and m.status != "RECONCILED"]
        if open_ic:
            reasons.append(f"{len(open_ic)} operacion(es) intercompania sin conciliar")
        pend = [f for f in findings if f.period == p and f.severity in (WARN, BLOCK)
                and f.rule_id not in {"SIGN-01", "IC-01"}]      # ya contados como bloqueado / IC abierta
        if pend:
            reasons.append(f"{len(pend)} alerta(s) pendiente(s) de revision")

        amounts = {c: ln.amount_usd for c, ln in lines.items()}
        gross = {c: ln.gross_usd for c, ln in lines.items()}
        out[p] = PeriodResult(p, cfg.periods.get(p, "desconocido"), lines, summarize(amounts, cfg),
                              summarize(gross, cfg), excluded, dict(by_status), not_conv, missing,
                              bool(reasons), reasons)
    return out


def trace(period: str, account_code: str, run) -> dict:
    """Desglose de una cifra del consolidado hasta sus filas fuente, tasas y ajustes."""
    pr = run.periods[period]
    ln = pr.lines[account_code]
    recs = {r.record_id: r for r in run.records}
    adjs = {a.adjustment_id: a for a in run.adjustments}
    return {
        "period": period, "account_code": account_code, "account_name": run.config.catalog[account_code].name,
        "amount_usd": ln.amount_usd, "gross_usd": ln.gross_usd,
        "records": [{"record_id": rid, "company_id": recs[rid].company_id, "file": recs[rid].source_file,
                     "sheet": recs[rid].source_sheet, "row": recs[rid].source_row,
                     "account_local": recs[rid].account_local, "amount_original": recs[rid].amount_original,
                     "currency": recs[rid].currency, "fx_rate": recs[rid].fx_rate,
                     "fx_orientation": recs[rid].fx_orientation, "amount_usd": recs[rid].amount_usd,
                     "counterparty_id": recs[rid].counterparty_id, "transaction_id": recs[rid].transaction_id}
                    for rid in ln.record_ids],
        "adjustments": [{"adjustment_id": aid, "kind": adjs[aid].kind, "amount_usd": adjs[aid].amount_usd,
                         "reason": adjs[aid].reason, "rule": adjs[aid].rule} for aid in ln.adjustment_ids],
    }
