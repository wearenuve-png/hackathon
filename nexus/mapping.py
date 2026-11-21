"""Homologacion de encabezados, cuentas y contrapartes.

El vocabulario de encabezados es generico (sinonimos contables en espanol e ingles).
Si un encabezado no se reconoce, queda sin mapear; la IA solo podra PROPONER (ai.py).
"""
from typing import Dict, List, Optional, Tuple

from .schemas import GroupConfig
from .text import norm

HEADER_ALIASES = {
    "period": {"periodo", "period", "mes", "month", "fecha", "date", "fecha contable"},
    "account": {"cuenta", "cuenta contable", "account", "account name", "concepto", "cuenta local", "rubro"},
    "amount": {"monto", "importe", "valor", "amount", "value", "saldo"},
    "currency": {"moneda", "divisa", "currency", "moneda de reporte", "reporting currency"},
    "counterparty": {"contraparte", "empresa relacionada", "counterparty", "cia relacionada",
                     "compania relacionada", "related party", "cliente proveedor"},
    "transaction_id": {"no factura", "numero de factura", "factura", "referencia", "documento", "invoice id",
                       "invoice", "transaction id", "num doc", "id transaccion", "reference", "doc"},
    "description": {"descripcion", "description", "detalle", "glosa"},
}
REQUIRED = ("period", "account", "amount")
_LOOKUP = {alias: field for field, aliases in HEADER_ALIASES.items() for alias in aliases}


def map_headers(columns: List[str]) -> Tuple[Dict[str, str], List[str]]:
    mapping, unmapped = {}, []
    for c in columns:
        f = _LOOKUP.get(norm(c))
        if f and f not in mapping.values():
            mapping[c] = f
        elif c is not None and norm(c):
            unmapped.append(c)
    return mapping, unmapped


def header_score(cells) -> int:
    """Cuantos campos obligatorios reconoce una fila candidata a encabezado."""
    found = {_LOOKUP.get(norm(c)) for c in cells if c is not None}
    return sum(1 for r in REQUIRED if r in found)


def map_account(company_id: str, local_name: str, cfg: GroupConfig) -> Optional[str]:
    """Equivalencia exacta por empresa. No adivina: sin equivalencia -> None (pendiente)."""
    return cfg.equivalences.get((company_id, norm(local_name)))


def map_counterparty(text: str, cfg: GroupConfig) -> Optional[str]:
    """Empresa del grupo por id, nombre o alias exacto (normalizado). Externo -> None."""
    t = norm(text)
    if not t:
        return None
    for c in cfg.companies.values():
        if t in {norm(c.company_id), norm(c.name)} | {norm(a) for a in c.aliases}:
            return c.company_id
    return None


FILE_CURRENCY_KEYS = {"currency", "moneda", "reporting currency", "moneda de reporte", "divisa"}


def file_currency_key(meta):
    """Clave de nivel archivo que declara la moneda (p. ej. JSON con reporting_currency), o None."""
    for k, v in (meta or {}).items():
        if norm(k) in FILE_CURRENCY_KEYS and v not in (None, ""):
            return k
    return None
