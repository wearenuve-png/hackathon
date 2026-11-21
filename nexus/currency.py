"""Conversion a USD. Convencion del grupo: usd_por_unidad_local, se multiplica."""
from decimal import Decimal
from typing import List
from .schemas import FxRate, GroupConfig, Record


def to_usd_multiply(amount: Decimal, usd_per_local: Decimal) -> Decimal:
    raise NotImplementedError


def to_usd_divide(amount: Decimal, local_per_usd: Decimal) -> Decimal:
    raise NotImplementedError


def to_usd(amount: Decimal, rate: FxRate) -> Decimal:
    raise NotImplementedError


def convert(records: List[Record], cfg: GroupConfig) -> List[Record]:
    raise NotImplementedError
