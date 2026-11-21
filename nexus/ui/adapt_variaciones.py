"""Adaptador para la interfaz rediseñada: app.py llama render(res, periodo) y tab_variaciones.render espera dos
ConsolidatedView (actual y previo). Calcula el periodo previo y llama correctamente; en el primer periodo no hay
previo y la pestana lo dice (nunca falla)."""
from typing import Optional

from ..variance import view
from . import tab_variaciones


def periodo_previo(res, period: str) -> Optional[str]:
    ps = sorted(res.periods)
    i = ps.index(period)
    return ps[i - 1] if i > 0 else None


def render(res, period) -> None:
    prev = periodo_previo(res, period)
    tab_variaciones.render(view(res, period), view(res, prev) if prev else None)
