"""Flujo completo: ingesta -> conversion -> reglas de registro -> intercompania -> consolidacion."""
import datetime as dt
from pathlib import Path

from . import audit, consolidation, currency, ingestion, intercompany, validation
from .config import load_group_config
from .schemas import BLOCK, WARN, Finding, RunResult


def run(input_dir, config_dir=None, ic_tolerance_usd="1.00") -> RunResult:
    input_dir = Path(input_dir)
    config_dir = Path(config_dir or input_dir)
    cfg = load_group_config(config_dir, ic_tolerance_usd)
    files = [input_dir / c.file for c in cfg.companies.values()] + sorted(config_dir.glob("*.csv"))
    hashes = audit.file_hashes([f for f in dict.fromkeys(files) if f.exists()])

    records = ingestion.ingest_group(input_dir, cfg)
    currency.convert(records, cfg)
    adjustments, findings = validation.apply_record_rules(records, cfg)
    matches = intercompany.match(records, cfg)
    adjustments += intercompany.eliminations(matches, records)
    for m in matches:
        if m.status != "RECONCILED":
            findings.append(Finding(f"F-IC-{m.match_id}", "IC-01", WARN if m.status == "DISCREPANCY" else BLOCK,
                                    f"{m.seller_id} registra {m.seller_usd:,.2f} USD y {m.buyer_id} registra "
                                    f"{m.buyer_usd:,.2f} USD (ref {m.reference or 's/ref'}): diferencia "
                                    f"{m.difference_usd:,.2f} USD. No se elimina.",
                                    m.seller_record_ids + m.buyer_record_ids, m.period, m.seller_id,
                                    f"{m.seller_usd} vs {m.buyer_usd}", "montos iguales",
                                    "Conciliar con ambas empresas antes de eliminar"))
    findings += validation.validate(records, cfg)
    periods = consolidation.consolidate(records, adjustments, matches, findings, cfg)
    run_id = dt.datetime.now().strftime("run-%Y%m%d-%H%M%S")
    return RunResult(run_id, cfg, records, adjustments, matches, findings, periods, hashes)
