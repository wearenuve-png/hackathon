"""Pestana Hallazgos: una ficha por hallazgo, con contador por tipo y orden por impacto (sin IA).

    from nexus.ui.tab_hallazgos import render
    render(consolidado, periodo)        # consolidado = RunResult
"""
import pandas as pd
import streamlit as st

from ..diagnostico import NOMBRES, contador_por_tipo, diagnosticar, fmt


def _donde(f) -> pd.DataFrame:
    return pd.DataFrame([{"Empresa": u.company_id, "Archivo": u.file, "Hoja": u.sheet or "-",
                          "Fila": "-" if u.row is None else u.row, "Periodo": u.period or "-",
                          "Cuenta local": u.account_local or "-",
                          "Importe": "n/c" if u.importe is None else f"{fmt(u.importe)} {u.moneda or ''}".strip(),
                          "USD": fmt(u.usd), "Estado": u.status or "-"} for u in f.donde])


def _ficha(f) -> None:
    st.markdown(f"**Qué pasó.** {f.que_paso}")
    st.markdown("**Dónde**")
    st.dataframe(_donde(f), width="stretch", hide_index=True)
    est = " (estimación)" if f.impacto_estimado else ""
    st.markdown(f"**Por qué importa.** {f.por_que_importa}")
    st.markdown(f"- Impacto en USD{est}: **{fmt(f.impacto_usd)}**" if f.impacto_usd is not None
                else "- Impacto en USD: no cuantificable")
    st.markdown(f"- Impacto en utilidad: {f.impacto_utilidad}")
    st.markdown(f"**Causa probable.** {f.causa_probable}")
    st.markdown(f"**Acción humana recomendada.** {f.accion}")
    if f.candidatos:
        st.markdown(f"**Causas candidatas del desbalance** (diferencia D = {fmt(f.diferencia)} USD), en orden:")
        for c in f.candidatos:
            st.markdown(f"{c.orden}. {c.descripcion}")
            st.dataframe(pd.DataFrame([{"Empresa": u.company_id, "Fila": u.row, "Cuenta local": u.account_local,
                                        "Importe": f"{fmt(u.importe)} {u.moneda}", "USD": fmt(u.usd),
                                        "Estado": u.status} for u in c.registros]), width="stretch", hide_index=True)
    elif f.causa_identificada is False:
        st.warning("Causa no identificada. Registros más cercanos al desbalance:")
        st.dataframe(pd.DataFrame([{"Empresa": u.company_id, "Fila": u.row, "Cuenta local": u.account_local,
                                    "Importe": f"{fmt(u.importe)} {u.moneda}", "USD": fmt(u.usd)}
                                   for u in f.cercanos]), width="stretch", hide_index=True)


def mostrar_ficha(f) -> None:
    """Dibuja el contenido de una ficha (la usa tambien la demostracion de errores)."""
    _ficha(f)


def render(consolidado, periodo=None) -> None:
    st.subheader("Hallazgos: qué pasó, dónde, por qué importa y qué hacer")
    fichas = [f for f in diagnosticar(consolidado) if periodo is None or f.period in (None, periodo)]
    st.caption("Plantillas en español, sin IA. La causa siempre es **probable** (una hipótesis) y la acción la toma "
               "una persona: NEXUS no corrige ni convierte nada por su cuenta. Orden: mayor impacto en USD primero.")
    if not fichas:
        st.success("Sin hallazgos en este período.")
        return
    cont = contador_por_tipo(fichas)
    cols = st.columns(min(4, len(cont)))
    for i, (tipo, n) in enumerate(cont.items()):
        cols[i % len(cols)].metric(NOMBRES[tipo], n)
    st.caption(f"{len(fichas)} hallazgo(s) en total.")
    for f in fichas:
        etiqueta = f"{f.ficha_id} · {NOMBRES[f.tipo]} · {f.company_id or '-'} · {f.period or '-'} · " \
                   f"{'n/c' if f.impacto_usd is None else fmt(f.impacto_usd) + ' USD'}"
        with st.expander(etiqueta):
            _ficha(f)
