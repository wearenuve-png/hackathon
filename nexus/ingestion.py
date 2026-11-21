"""Fachada de la ingesta. La logica vive en nexus/adapters/ (extract + normalize por formato)
y los perfiles en nexus/profiles.py. Las firmas publicas se mantienen.

Nada se descarta en silencio: un dato invalido queda como registro BLOCKED/PENDING con su motivo, y una
fuente que no coincide con su perfil deja la carga de esa empresa en REVISION (LoadReport).
"""
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .adapters import EXT_TYPE, ProfileMismatch, adapter_for
from .profiles import shared_source_conflicts, validate_profile
from .schemas import CompanyProfile, GroupConfig, LoadReport, Record

READERS = {ext: (lambda p, _t=t: adapter_for(_t).extract(p)) for ext, t in EXT_TYPE.items()}


def ingest_file(path, company_id: str, cfg: GroupConfig, profile: Optional[CompanyProfile] = None) -> List[Record]:
    path = Path(path)
    stype = profile.source.type if profile else EXT_TYPE.get(path.suffix.lower())
    if stype is None:
        raise ValueError(f"Formato no soportado: {path.name}")
    records, _notes = adapter_for(stype).ingest(path, company_id, cfg, profile)
    return records


def ingest_group(input_dir, cfg: GroupConfig) -> List[Record]:
    """Modo legado (sin perfiles): deteccion automatica. Archivo faltante -> error explicito."""
    d = Path(input_dir)
    out = []
    for c in cfg.companies.values():
        p = d / c.file
        if not p.exists():
            raise FileNotFoundError(f"Falta el archivo de {c.company_id}: {p}")
        out.extend(ingest_file(p, c.company_id, cfg))
    return out


def ingest_group_with_reports(input_dir, cfg: GroupConfig,
                              profiles: Optional[Dict[str, CompanyProfile]] = None
                              ) -> Tuple[List[Record], Dict[str, LoadReport]]:
    """Con perfiles: cada empresa se lee SOLO con su perfil; si no coincide, queda en REVISION y no
    aporta registros (el periodo queda provisional). Sin perfiles: modo legado, estado AUTO."""
    d = Path(input_dir)
    records: List[Record] = []
    reports: Dict[str, LoadReport] = {}
    conflicts = shared_source_conflicts(profiles) if profiles else {}
    for cid, c in cfg.companies.items():
        rep = LoadReport(cid, c.file, "AUTO")
        reports[cid] = rep
        path = d / c.file
        if profiles is None:
            if not path.exists():
                raise FileNotFoundError(f"Falta el archivo de {cid}: {path}")
            rep.n_records = len(recs := ingest_file(path, cid, cfg))
            records.extend(recs)
            continue
        p = profiles.get(cid)
        if p is None:
            rep.status, rep.reasons = "REVIEW", ["La empresa no tiene perfil de integracion"]
            continue
        rep.profile_version, rep.approval_status, rep.file = p.profile_version, p.approval_status, p.source.file
        problems = validate_profile(p, cfg)
        problems += [f"El archivo {f} esta asignado a varias empresas: {', '.join(ids)}"
                     for f, ids in conflicts.items() if cid in ids]
        if problems:
            rep.status, rep.reasons = "REVIEW", ["Perfil invalido: " + x for x in problems]
            continue
        path = d / p.source.file
        if not path.exists():
            rep.status, rep.reasons = "REVIEW", [f"No se encontro el archivo {p.source.file}"]
            continue
        if EXT_TYPE.get(path.suffix.lower()) != p.source.type:
            rep.status = "REVIEW"
            rep.reasons = [f"El archivo es {path.suffix} pero el perfil declara {p.source.type}"]
            continue
        try:
            recs, notes = adapter_for(p.source.type).ingest(path, cid, cfg, p)
        except ProfileMismatch as e:
            rep.status, rep.reasons = "REVIEW", e.reasons
            continue
        rep.status, rep.notes, rep.n_records = "MATCHED", notes, len(recs)
        records.extend(recs)
    return records, reports
