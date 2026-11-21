"""Simulador de tipo de cambio: ¿que pasaria con el consolidado y los indicadores si la tasa de una moneda
fuera un % distinta? Es una SIMULACION: se recalcula todo en memoria con las tasas escaladas; no modifica datos,
tasas, perfiles ni archivos (los archivos se leen en solo lectura, como siempre)."""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional

from .metrics import IndicatorParams, compute_indicators, load_params
from .pipeline import run

MAX_PCT = Decimal("10")
ETIQUETA = "SIMULACIÓN"
SUMMARY_ROWS = [("Ingresos", "ingresos"), ("Costo de ventas", "costo_ventas"),
                ("Gastos operativos", "gastos_operativos"), ("EBIT", "ebit"), ("Utilidad neta", "utilidad_neta"),
                ("Activo total", "activo_total"), ("Pasivo total", "pasivo_total"), ("Patrimonio", "patrimonio")]


def scale_factors(pcts: Dict[str, Decimal]) -> Dict[str, Decimal]:
    """{'MXN': +5, 'GTQ': -10} (en %) -> {'MXN': 1.05, 'GTQ': 0.90}. Rango permitido: -10 % a +10 %."""
    out = {}
    for cur, pct in pcts.items():
        pct = Decimal(str(pct))
        if not (-MAX_PCT <= pct <= MAX_PCT):
            raise ValueError(f"La variacion de {cur} debe estar entre -10 % y +10 % (recibido {pct} %)")
        out[cur] = 1 + pct / 100
    return out


def simulate(input_dir, profiles_dir=None, pcts: Optional[Dict[str, Decimal]] = None, config_dir=None,
             ic_tolerance_usd="1.00"):
    """RunResult recalculado con las tasas escaladas. No escribe nada."""
    return run(input_dir, config_dir, ic_tolerance_usd, profiles_dir, rate_scale=scale_factors(pcts or {}))


@dataclass
class SimRow:
    label: str
    original: Optional[Decimal]
    simulated: Optional[Decimal]

    @property
    def difference(self) -> Optional[Decimal]:
        return None if self.original is None or self.simulated is None else self.simulated - self.original


@dataclass
class SimComparison:
    period: str
    pcts: Dict[str, Decimal]
    summary: List[SimRow] = field(default_factory=list)
    indicators: List[SimRow] = field(default_factory=list)
    open_ic_original: int = 0
    open_ic_simulated: int = 0
    label: str = ETIQUETA


def compare(base, sim, period: str, pcts=None, params: Optional[IndicatorParams] = None) -> SimComparison:
    params = params or load_params()
    b, s = base.periods[period].summary, sim.periods[period].summary
    out = SimComparison(period, dict(pcts or {}))
    out.summary = [SimRow(lbl, b[k], s[k]) for lbl, k in SUMMARY_ROWS]
    ib, is_ = compute_indicators(base, period, params), compute_indicators(sim, period, params)
    for lbl, attr in (("NOPAT", "nopat"), ("Capital invertido", "invested_capital"),
                      ("ROIC (mensual)", "roic"), ("ROCE (mensual)", "roce"), ("EVA (mensual, USD)", "eva")):
        out.indicators.append(SimRow(lbl, getattr(ib, attr), getattr(is_, attr)))
    out.open_ic_original = sum(1 for m in base.matches if m.period == period and m.status != "RECONCILED")
    out.open_ic_simulated = sum(1 for m in sim.matches if m.period == period and m.status != "RECONCILED")
    return out
