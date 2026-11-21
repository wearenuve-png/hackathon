"""Adaptador para la interfaz rediseñada (app.py llama render(res, periodo) a cada pestaña).
tab_indicadores.render ya recibe (consolidado, periodo); el adaptador existe para que ambas pestañas se carguen
igual y para aislar a app.py de cambios futuros en esa firma."""
from . import tab_indicadores


def render(res, period) -> None:
    tab_indicadores.render(res, period)
