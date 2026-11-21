"""Nivel de confianza de un periodo: cuantos registros estan limpios y por que el periodo es PROVISIONAL.
Es una regla simple y visible (no estadistica):
    ALTA   periodo definitivo y >= 99 % de registros limpios
    MEDIA  >= 95 % de registros limpios y sin empresas faltantes
    BAJA   en cualquier otro caso
Limpio = registro que entra al consolidado (estado OK). Los registros OK con una alerta de revision se cuentan
aparte ('con alerta') pero siguen siendo limpios."""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import List

from .schemas import BLOCKED, EXCLUDED_DUPLICATE, OK, PENDING_MAPPING, TOTAL

ALTA, MEDIA, BAJA = "ALTA", "MEDIA", "BAJA"
UMBRAL_ALTA, UMBRAL_MEDIA = Decimal("0.99"), Decimal("0.95")


@dataclass
class Confidence:
    period: str
    total: int
    limpios: int
    con_alerta: int
    bloqueados: int
    pendientes: int
    duplicados: int
    pct_limpios: Decimal
    nivel: str
    provisional: bool
    motivos: List[str] = field(default_factory=list)


def confidence(run, period: str) -> Confidence:
    pr = run.periods[period]
    recs = [r for r in run.records if r.period == period and r.status != TOTAL]
    n = len(recs)
    limpios = sum(1 for r in recs if r.status == OK)
    con_alerta = sum(1 for r in recs if r.status == OK and r.flags)
    bloq = sum(1 for r in recs if r.status == BLOCKED)
    pend = sum(1 for r in recs if r.status == PENDING_MAPPING)
    dup = sum(1 for r in recs if r.status == EXCLUDED_DUPLICATE)
    pct = Decimal(limpios) / Decimal(n) if n else Decimal(0)
    if not pr.provisional and pct >= UMBRAL_ALTA:
        nivel = ALTA
    elif pct >= UMBRAL_MEDIA and not pr.missing_companies:
        nivel = MEDIA
    else:
        nivel = BAJA
    return Confidence(period, n, limpios, con_alerta, bloq, pend, dup, pct, nivel, pr.provisional,
                      list(pr.provisional_reasons))
