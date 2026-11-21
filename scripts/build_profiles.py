"""Genera los perfiles de integracion (profiles/EMPxxx.json) a partir de empresas.csv,
equivalencias.csv y la lectura de cada archivo. Versiona: si el contenido cambia, sube la version.

    .venv/bin/python scripts/build_profiles.py [--data data/synthetic] [--out profiles] [--approved-by "Nombre"]

Sin --approved-by los perfiles quedan en estado PENDING (se usan, pero se muestran como pendientes).
"""
import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from nexus import ingestion  # noqa: E402
from nexus.config import load_group_config  # noqa: E402
from nexus.profiles import ProfileError, build_profile, load_profiles, save_profile, validate_profile  # noqa: E402

TYPE_BY_EXT = {".xlsx": "xlsx", ".xlsm": "xlsx", ".csv": "csv", ".txt": "csv", ".json": "json"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/synthetic")
    ap.add_argument("--out", default="profiles")
    ap.add_argument("--approved-by", default=None)
    a = ap.parse_args()
    data, out = Path(a.data), Path(a.out)
    cfg = load_group_config(data)
    names = {}
    with open(data / "equivalencias.csv", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            names.setdefault(r["company_id"], {})[r["cuenta_local"]] = r["account_code"]
    existing = load_profiles(out) if out.exists() else {}
    for c in cfg.companies.values():
        path = data / c.file
        ext = path.suffix.lower()
        tables = ingestion.READERS[ext](path)
        p = build_profile(c, tables, names.get(c.company_id, {}), TYPE_BY_EXT[ext], existing.get(c.company_id),
                          a.approved_by)
        problems = validate_profile(p, cfg)
        if problems:
            raise ProfileError(f"{c.company_id}: " + "; ".join(problems))
        save_profile(p, out)
        print(f"{c.company_id}: {p.source.type:<5} v{p.profile_version} {p.approval_status:<8} {c.file}")


if __name__ == "__main__":
    main()
