"""Reenvio entre ejecuciones: compara los archivos y los IDs de transaccion de la carga actual contra las
ejecuciones anteriores guardadas por audit.write_run (carpeta data/output/run-*/). Solo ADVIERTE; no excluye nada.

    REE-01  el archivo (mismo SHA-256) ya fue cargado en otra ejecucion
    REE-02  el archivo cambio, pero repite IDs de transaccion ya cargados antes (p. ej. una version corregida)
"""
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Dict, List, Optional

from .schemas import OK, WARN, Finding


def _cuando(run_dir: Path) -> str:
    try:
        return dt.datetime.strptime(run_dir.name, "run-%Y%m%d-%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return dt.datetime.fromtimestamp(run_dir.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")


def previous_runs(history_dir) -> List[dict]:
    """Ejecuciones guardadas (mas reciente primero): id, fecha, hashes de entrada y IDs de transaccion."""
    out = []
    d = Path(history_dir)
    if not d.is_dir():
        return out
    for rd in sorted((p for p in d.glob("run-*") if (p / "run.json").is_file()), key=lambda p: p.name, reverse=True):
        try:
            meta = json.loads((rd / "run.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        ids = set()
        rec = rd / "records.csv"
        if rec.is_file():
            with open(rec, encoding="utf-8", newline="") as f:
                for r in csv.DictReader(f):
                    if r.get("transaction_id"):
                        ids.add((r["company_id"], r["period"], r["transaction_id"]))
        out.append({"run_id": meta.get("run_id", rd.name), "cuando": _cuando(rd),
                    "hashes": meta.get("input_hashes", {}), "ids": ids})
    return out


def detect_resend(records, cfg, hashes: Dict[str, str], history_dir) -> List[Finding]:
    prev = previous_runs(history_dir)
    if not prev:
        return []
    out: List[Finding] = []
    for c in cfg.companies.values():
        h = hashes.get(c.file)
        if not h:
            continue
        hit = next((p for p in prev if h in p["hashes"].values()), None)
        if hit:
            out.append(Finding(f"F-REE-{c.company_id}", "REE-01", WARN,
                               f"Posible reenvio: el archivo {c.file} (SHA-256 {h[:16]}...) ya fue cargado en la "
                               f"ejecucion {hit['run_id']} del {hit['cuando']}.", [], None, c.company_id, h[:16],
                               "archivo nuevo", "Confirmar que no se este consolidando dos veces la misma informacion"))
            continue
        mine = [r for r in records if r.company_id == c.company_id and r.status == OK and r.transaction_id]
        for p in prev:
            rep = [r for r in mine if (r.company_id, r.period, r.transaction_id) in p["ids"]]
            if rep:
                muestra = ", ".join(sorted({r.transaction_id for r in rep})[:3])
                out.append(Finding(f"F-REE-{c.company_id}-ID", "REE-02", WARN,
                                   f"Posible reenvio: {len(rep)} registro(s) de {c.company_id} repiten IDs de "
                                   f"transaccion ya cargados en la ejecucion {p['run_id']} del {p['cuando']} "
                                   f"(por ejemplo {muestra}), aunque el archivo {c.file} cambio.",
                                   [r.record_id for r in rep], None, c.company_id, f"{len(rep)} ID(s) repetidos",
                                   "IDs nuevos", "Confirmar si es una version corregida del mismo archivo o una "
                                   "carga duplicada"))
                break
    return out
