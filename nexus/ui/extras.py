"""Extras de la interfaz, conectados desde app.py con dos llamadas:

    extras.render_header(res, period, data_dir, profiles_dir)              # confianza + descarga
    extras.render_extra_tabs(res, period, data_dir, profiles_dir, tab_ind, tab_var, tab_sim, tab_help)
"""
from decimal import Decimal

import streamlit as st

from ..audit import build_audit_package
from ..confidence import ALTA, MEDIA, confidence
from ..variance import view
from . import tab_ayuda, tab_indicadores, tab_simulador, tab_variaciones


def render_confianza(res, period) -> None:
    c = confidence(res, period)
    nivel = {ALTA: st.success, MEDIA: st.warning}.get(c.nivel, st.error)
    with st.container(border=True):
        nivel(f"Nivel de confianza del periodo: {c.nivel}")
        a, b = st.columns(2)
        a.metric("Registros limpios", f"{c.limpios} de {c.total} ({c.pct_limpios:.1%})")
        b.metric("Bloqueados / pendientes / duplicados excluidos", f"{c.bloqueados} / {c.pendientes} / {c.duplicados}")
        st.progress(float(c.pct_limpios))
        if c.con_alerta:
            st.caption(f"{c.con_alerta} registro(s) limpios llevan una alerta de revision (siguen en el consolidado).")
        if c.provisional:
            st.markdown("**Por qué es PROVISIONAL:** " + "; ".join(c.motivos))
        st.caption("Regla simple: ALTA = definitivo y ≥ 99 % limpio; MEDIA = ≥ 95 % y sin empresas faltantes; "
                   "BAJA = el resto.")


def render_descarga(res, period, data_dir) -> None:
    st.download_button("Descargar paquete de auditoría", data=build_audit_package(res, source_dir=data_dir),
                       file_name=f"paquete_auditoria_{res.run_id}.zip", mime="application/zip",
                       help="Consolidado, ajustes, alertas, discrepancias, perfiles y hashes SHA-256 (zip).")


def render_header(res, period, data_dir, profiles_dir) -> None:
    render_confianza(res, period)
    render_descarga(res, period, data_dir)


def render_extra_tabs(res, period, data_dir, profiles_dir, tab_ind, tab_var, tab_sim, tab_help) -> None:
    with tab_ind:
        tab_indicadores.render(res, period)
    with tab_var:
        ps = sorted(res.periods)
        i = ps.index(period)
        tab_variaciones.render(view(res, period), view(res, ps[i - 1]) if i > 0 else None)
    with tab_sim:
        tab_simulador.render(res, period, data_dir, profiles_dir)
    with tab_help:
        tab_ayuda.render()
