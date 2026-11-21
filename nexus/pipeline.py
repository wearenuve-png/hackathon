"""Flujo completo: ingesta -> conversion -> reglas de registro -> intercompania -> consolidacion."""
import datetime as dt
from pathlib import Path

from . import audit, consolidation, currency, ingestion, intercompany, validation
from .config import load_group_config
from .profiles import apply_profiles, load_profiles
from .schemas import BLOCK, WARN, Finding, RunResult


def run(input_dir, config_dir=None, ic_tolerance_usd="1.00", profiles_dir=None) -> RunResult:
    """profiles_dir=None: modo legado (deteccion automatica). Con perfiles: cada empresa se lee solo con
    el suyo y una fuente que no coincide queda en REVISION (no se procesa en silencio)."""
    input_dir = Path(input_dir)
    config_dir = Path(config_dir or input_dir)
    cfg = load_group_config(config_dir, ic_tolerance_usd)
    profiles = None
    if profiles_dir is not None:
        profiles = load_profiles(profiles_dir)
        apply_profiles(cfg, profiles)
    files = [input_dir / c.file for c in cfg.companies.values()] + sorted(config_dir.glob("*.csv"))
    if profiles_dir is not None:
        files += sorted(Path(profiles_dir).glob("*.json"))
    hashes = audit.file_hashes([f for f in dict.fromkeys(files) if f.exists()])

    records, load_reports = ingestion.ingest_group_with_reports(input_dir, cfg, profiles)
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
    for rep in load_reports.values():
        if rep.status == "REVIEW":
            findings.append(Finding(f"F-CARGA-{rep.company_id}", "CARGA-01", BLOCK,
                                    f"La carga de {rep.company_id} ({rep.file}) quedo en REVISION y no aporta "
                                    f"registros: " + "; ".join(rep.reasons), [], None, rep.company_id,
                                    suggestion="Corregir el archivo o actualizar y aprobar el perfil"))
    by_hash = {}
    for c in cfg.companies.values():
        h = hashes.get(c.file)
        if h:
            by_hash.setdefault(h, []).append(c)
    for h, cs in by_hash.items():
        if len(cs) > 1:
            findings.append(Finding(f"F-ARC-{cs[0].company_id}", "ARC-01", WARN,
                                    "Los archivos " + " y ".join(c.file for c in cs) + " son identicos (mismo "
                                    f"SHA-256 {h[:16]}...): posible reenvio del mismo archivo bajo otro nombre.",
                                    [], None, cs[0].company_id, h[:16], "archivos distintos",
                                    "Confirmar cual es el archivo correcto de cada empresa"))
    findings += validation.validate(records, cfg)
    periods = consolidation.consolidate(records, adjustments, matches, findings, cfg)
    run_id = dt.datetime.now().strftime("run-%Y%m%d-%H%M%S")
    return RunResult(run_id, cfg, records, adjustments, matches, findings, periods, hashes, load_reports)
