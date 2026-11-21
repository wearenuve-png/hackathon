"""Perfiles de integracion por empresa: configuracion validada y versionada.

Un perfil dice COMO leer la fuente de una empresa (formato, encabezados, moneda, signo, cuentas).
El motor no contiene reglas particulares de ninguna empresa: todo lo particular vive aqui.
"""
import dataclasses
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Dict, List

from .schemas import (CURRENCY_MODES, SIGN_DEBIT_CREDIT, SIGN_SIGNED, SOURCE_TYPES, SUPPORTED_PROFILE_SCHEMA,
                      Company, CompanyProfile, GroupConfig, SourceSpec)
from .text import norm

APPROVAL_PENDING = "PENDING"
APPROVAL_OK = "APPROVED"
_NON_CONTENT = {"profile_version", "approved_by", "approved_at", "approval_status", "profile_hash"}


class ProfileError(Exception):
    pass


# ---------------------------------------------------------------- (de)serializacion
def to_dict(p: CompanyProfile) -> dict:
    d = dataclasses.asdict(p)
    return d


def from_dict(d: dict) -> CompanyProfile:
    try:
        src = d["source"]
        return CompanyProfile(
            company_id=d["company_id"], company_name=d.get("company_name", d["company_id"]),
            country=d.get("country", ""), functional_currency=d["functional_currency"],
            source=SourceSpec(src["type"], src["file"]), columns=dict(d["columns"]),
            accounts=dict(d.get("accounts", {})), sheets=list(d.get("sheets", [])),
            sign_convention=d.get("sign_convention", SIGN_SIGNED),
            currency_mode=d.get("currency_mode", "company_config"), currency_key=d.get("currency_key"),
            counterparty_aliases=list(d.get("counterparty_aliases", [])),
            schema_version=d.get("schema_version", SUPPORTED_PROFILE_SCHEMA),
            profile_version=d.get("profile_version", 1), approval_status=d.get("approval_status", APPROVAL_PENDING),
            approved_by=d.get("approved_by"), approved_at=d.get("approved_at"), profile_hash=d.get("profile_hash", ""))
    except (KeyError, TypeError) as e:
        raise ProfileError(f"Perfil mal formado: falta o es invalido {e}") from e


def content_hash(p: CompanyProfile) -> str:
    """Hash del contenido que cambia el comportamiento (no incluye version ni aprobacion)."""
    d = {k: v for k, v in to_dict(p).items() if k not in _NON_CONTENT}
    return hashlib.sha256(json.dumps(d, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def save_profile(p: CompanyProfile, directory) -> Path:
    p.profile_hash = content_hash(p)
    path = Path(directory) / f"{p.company_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(to_dict(p), indent=2, ensure_ascii=False, sort_keys=False) + "\n", encoding="utf-8")
    return path


def load_profiles(directory) -> Dict[str, CompanyProfile]:
    out = {}
    for f in sorted(Path(directory).glob("*.json")):
        p = from_dict(json.loads(f.read_text(encoding="utf-8")))
        if p.company_id in out:
            raise ProfileError(f"Perfil duplicado para {p.company_id}")
        out[p.company_id] = p
    return out


# ---------------------------------------------------------------- validacion
def validate_profile(p: CompanyProfile, cfg: GroupConfig) -> List[str]:
    """Lista de problemas; vacia = perfil valido. Un perfil invalido deja la carga en revision."""
    errs = []
    if p.schema_version != SUPPORTED_PROFILE_SCHEMA:
        errs.append(f"schema_version {p.schema_version} no soportado (se espera {SUPPORTED_PROFILE_SCHEMA})")
    if p.source.type not in SOURCE_TYPES:
        errs.append(f"Tipo de fuente desconocido: {p.source.type!r}")
    if not p.source.file:
        errs.append("El perfil no declara archivo")
    if p.sign_convention not in {SIGN_SIGNED, SIGN_DEBIT_CREDIT}:
        errs.append(f"Convencion de signo desconocida: {p.sign_convention!r}")
    cols = p.columns
    need = ["period", "account"] + (["debit", "credit"] if p.sign_convention == SIGN_DEBIT_CREDIT else ["amount"])
    errs += [f"Falta la columna canonica '{f}'" for f in need if f not in cols]
    heads = [norm(h) for h in cols.values()]
    if len(set(heads)) != len(heads):
        errs.append("Dos campos apuntan al mismo encabezado")
    if p.currency_mode not in CURRENCY_MODES:
        errs.append(f"Modo de moneda desconocido: {p.currency_mode!r}")
    elif p.currency_mode == "column" and "currency" not in cols:
        errs.append("currency_mode=column exige la columna 'currency'")
    elif p.currency_mode == "file_key" and not p.currency_key:
        errs.append("currency_mode=file_key exige currency_key")
    known = {c for (_p, c) in cfg.rates} | {cfg.base_currency}
    if p.functional_currency not in known:
        errs.append(f"Moneda funcional sin tasas: {p.functional_currency!r}")
    seen = {}
    for local, code in p.accounts.items():
        if code not in cfg.catalog:
            errs.append(f"Cuenta {local!r} apunta a un codigo que no existe en el catalogo: {code!r}")
        n = norm(local)
        if n in seen and seen[n] != code:
            errs.append(f"La cuenta {local!r} esta mapeada a dos codigos distintos")
        seen[n] = code
    if p.approval_status not in {APPROVAL_PENDING, APPROVAL_OK}:
        errs.append(f"Estado de aprobacion desconocido: {p.approval_status!r}")
    if p.approval_status == APPROVAL_OK and not p.approved_by:
        errs.append("Perfil APPROVED sin approved_by")
    if p.profile_hash and p.profile_hash != content_hash(p):
        errs.append("El contenido del perfil cambio sin actualizar su version/hash (editado a mano)")
    return errs


def shared_source_conflicts(profiles: Dict[str, CompanyProfile]) -> Dict[str, List[str]]:
    """Dos empresas no pueden apuntar al mismo archivo: asi las fuentes no se mezclan."""
    by_file: Dict[str, List[str]] = {}
    for cid, p in profiles.items():
        by_file.setdefault(p.source.file, []).append(cid)
    return {f: ids for f, ids in by_file.items() if len(ids) > 1}


# ---------------------------------------------------------------- aplicar al grupo
def apply_profiles(cfg: GroupConfig, profiles: Dict[str, CompanyProfile]) -> GroupConfig:
    """El perfil es la autoridad de cada empresa: archivo, moneda funcional, alias y equivalencias.
    Una empresa nueva existe en el grupo solo con tener perfil."""
    for cid, p in profiles.items():
        existing = cfg.companies.get(cid)
        cfg.companies[cid] = Company(cid, p.company_name or (existing.name if existing else cid),
                                     p.country or (existing.country if existing else ""),
                                     p.functional_currency, p.source.file, list(p.counterparty_aliases))
        for k in [k for k in cfg.equivalences if k[0] == cid]:
            del cfg.equivalences[k]
        for local, code in p.accounts.items():
            cfg.equivalences[(cid, norm(local))] = code
    cfg.profiles = dict(profiles)
    return cfg


# ---------------------------------------------------------------- construir desde los CSV del grupo
def build_profile(company: Company, tables, accounts: Dict[str, str], source_type: str, existing=None,
                  approved_by=None) -> CompanyProfile:
    """tables: lista de Table leidas del archivo de la empresa; accounts: nombre local -> codigo
    (de equivalencias.csv, con el nombre original sin normalizar)."""
    from .mapping import map_headers
    if not tables:
        raise ProfileError(f"{company.company_id}: no se encontro ninguna tabla reconocible en {company.file}")
    maps = []
    for t in tables:
        mapping, _ = map_headers(t.header)
        maps.append({f: c for c, f in mapping.items()})
    if any(m != maps[0] for m in maps[1:]):
        raise ProfileError(f"{company.company_id}: las hojas de {company.file} no usan los mismos encabezados")
    columns = {f: str(c) for f, c in maps[0].items()}
    cur_mode, cur_key = "company_config", None
    if "currency" in columns:
        cur_mode, cur_key = "column", columns["currency"]
    else:
        from .mapping import file_currency_key
        for t in tables:
            k = file_currency_key(t.meta)
            if k:
                cur_mode, cur_key = "file_key", k
                break
    sheets = [t.sheet for t in tables if t.sheet]
    sign = SIGN_DEBIT_CREDIT if "amount" not in columns and {"debit", "credit"} <= set(columns) else SIGN_SIGNED
    p = CompanyProfile(
        company_id=company.company_id, company_name=company.name, country=company.country,
        functional_currency=company.currency, source=SourceSpec(source_type, company.file), columns=columns,
        accounts=dict(sorted(accounts.items())), sheets=sheets, sign_convention=sign,
        currency_mode=cur_mode, currency_key=cur_key, counterparty_aliases=list(company.aliases))
    p.profile_hash = content_hash(p)
    prev_v = existing.profile_version if existing else 0
    if existing and existing.profile_hash == p.profile_hash:
        p.profile_version = existing.profile_version
        p.approved_by, p.approved_at, p.approval_status = (existing.approved_by, existing.approved_at,
                                                           existing.approval_status)
    else:
        p.profile_version = prev_v + 1
    if approved_by:
        p.approved_by, p.approval_status = approved_by, APPROVAL_OK
        p.approved_at = dt.date.today().isoformat()
    return p
