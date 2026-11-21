"""Consolidado por periodo y cuenta, con trazabilidad y exclusiones visibles."""
from typing import Dict, List
from .schemas import Adjustment, Finding, GroupConfig, ICMatch, PeriodResult, Record


def consolidate(records: List[Record], adjustments: List[Adjustment], matches: List[ICMatch],
                findings: List[Finding], cfg: GroupConfig) -> Dict[str, PeriodResult]:
    raise NotImplementedError


def trace(period: str, account_code: str, run) -> dict:
    raise NotImplementedError
