"""Registro de ejecuciones: hashes de entrada, version de reglas y salidas reproducibles."""
import csv
import hashlib
import json
from decimal import Decimal
from pathlib import Path


def file_hashes(paths) -> dict:
    return {Path(p).name: sha256_file(p) for p in paths}


def sha256_file(path) -> str:
    """Lectura en bloques, solo lectura: nunca abre el archivo en modo escritura."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_hashes(hashes: dict, dirs) -> dict:
    """Vuelve a calcular el SHA-256 de cada archivo registrado: OK (igual), CAMBIO (distinto) o FALTA."""
    out = {}
    for name, registered in hashes.items():
        path = next((Path(d) / name for d in dirs if (Path(d) / name).is_file()), None)
        if path is None:
            out[name] = {"status": "FALTA", "registered": registered, "current": None}
            continue
        cur = sha256_file(path)
        out[name] = {"status": "OK" if cur == registered else "CAMBIO", "registered": registered, "current": cur,
                     "path": str(path)}
    return out


def _default(o):
    if isinstance(o, Decimal):
        return str(o)
    if hasattr(o, "isoformat"):
        return o.isoformat()
    if hasattr(o, "__dict__"):
        return o.__dict__
    return str(o)


def write_run(run, output_dir, source_dir=None) -> str:
    """source_dir (opcional): carpeta del servidor de donde se leyeron los archivos; queda en la evidencia."""
    d = Path(output_dir) / run.run_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "run.json").write_text(json.dumps({
        "run_id": run.run_id, "rules_version": run.config.rules_version,
        "source": {"kind": "server_folder", "mode": "read_only", "path": str(source_dir) if source_dir else None,
                   "network": "none"},
        "ic_tolerance_usd": run.config.ic_tolerance_usd, "input_hashes": run.input_hashes,
        "periods": {p: {"kind": pr.kind, "provisional": pr.provisional, "provisional_reasons": pr.provisional_reasons,
                        "summary": pr.summary, "naive_summary": pr.naive_summary,
                        "lines": {c: {"amount_usd": ln.amount_usd, "gross_usd": ln.gross_usd}
                                  for c, ln in pr.lines.items()},
                        "excluded": pr.excluded, "excluded_usd_by_status": pr.excluded_usd_by_status,
                        "missing_companies": pr.missing_companies}
                    for p, pr in run.periods.items()},
        "load_reports": run.load_reports, "matches": run.matches, "adjustments": run.adjustments, "findings": run.findings,
    }, default=_default, indent=2, ensure_ascii=False), encoding="utf-8")
    with open(d / "records.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        cols = ["record_id", "company_id", "source_file", "source_sheet", "source_row", "period", "account_local",
                "account_code", "amount_original", "currency", "fx_rate", "fx_orientation", "amount_usd", "status",
                "status_reasons", "flags", "counterparty_id", "transaction_id", "ic_match_id", "adjustment_ids"]
        w.writerow(cols)
        for r in run.records:
            w.writerow([getattr(r, c) if not isinstance(getattr(r, c), list) else "; ".join(getattr(r, c))
                        for c in cols])
    return str(d)
