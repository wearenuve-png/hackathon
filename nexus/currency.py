"""Conversion a USD con la tasa del mes.

Convencion del grupo: tasas.csv trae `usd_por_unidad_local` y se MULTIPLICA.
El caso inverso (`local_por_usd`, se divide) tiene su propia funcion explicita.
Sin redondeo interno: se guarda el Decimal completo; se redondea solo al presentar.
"""
from decimal import Decimal
from typing import List

from .schemas import BLOCKED, LOCAL_PER_USD, USD_PER_LOCAL, FxRate, GroupConfig, Record


def to_usd_multiply(amount: Decimal, usd_per_local: Decimal) -> Decimal:
    """80,000 GTQ x 0.125 USD/GTQ = 10,000 USD"""
    return amount * usd_per_local


def to_usd_divide(amount: Decimal, local_per_usd: Decimal) -> Decimal:
    """80,000 GTQ / 8 GTQ/USD = 10,000 USD"""
    if local_per_usd == 0:
        raise ZeroDivisionError("Tasa local_por_usd igual a cero")
    return amount / local_per_usd


def to_usd(amount: Decimal, rate: FxRate) -> Decimal:
    if rate.orientation == USD_PER_LOCAL:
        return to_usd_multiply(amount, rate.rate)
    if rate.orientation == LOCAL_PER_USD:
        return to_usd_divide(amount, rate.rate)
    raise ValueError(f"Orientacion de tasa desconocida: {rate.orientation}")


def known_currencies(cfg: GroupConfig):
    return {cur for (_p, cur) in cfg.rates} | {cfg.base_currency}


def convert(records: List[Record], cfg: GroupConfig) -> List[Record]:
    """Llena fx_rate, fx_orientation y amount_usd. Moneda vacia o desconocida, o sin tasa del mes:
    el registro queda BLOCKED (no se asume tasa 1 ni se infiere la moneda)."""
    valid = known_currencies(cfg)
    for r in records:
        if r.currency is None:
            r.block(BLOCKED, "Moneda faltante")
            continue
        if r.currency not in valid:
            r.block(BLOCKED, f"Moneda invalida o desconocida: {r.currency!r}")
            continue
        if r.amount_original is None or r.period is None:
            continue
        if r.currency == cfg.base_currency and (r.period, r.currency) not in cfg.rates:
            rate = FxRate(r.period, r.currency, Decimal(1), USD_PER_LOCAL)
        else:
            rate = cfg.rates.get((r.period, r.currency))
        if rate is None:
            r.block(BLOCKED, f"Sin tasa para {r.currency} en {r.period}")
            continue
        if rate.rate <= 0:
            r.block(BLOCKED, f"Tasa invalida ({rate.rate}) para {r.currency} en {r.period}: debe ser mayor que cero")
            continue
        r.fx_rate, r.fx_orientation = rate.rate, rate.orientation
        r.amount_usd = to_usd(r.amount_original, rate)
    return records
