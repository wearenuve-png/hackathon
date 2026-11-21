"""Pestana Simulador de tipo de cambio. SIMULACION: no modifica datos ni archivos."""
from decimal import Decimal

import pandas as pd
import streamlit as st

from ..simulator import ETIQUETA, MAX_PCT, compare, simulate

MONEDAS = ["MXN", "GTQ"]


def _m(d):
    return "n/c" if d is None else f"{d:,.2f}"


def _p(d):
    return "n/c" if d is None else f"{d:.2%}"


@st.cache_resource(show_spinner="Simulando...")
def _simular(data_dir, profiles_dir, mxn, gtq):
    return simulate(data_dir, profiles_dir or None, {"MXN": Decimal(str(mxn)), "GTQ": Decimal(str(gtq))})


def render(res, periodo, data_dir, profiles_dir) -> None:
    st.subheader("Simulador de tipo de cambio")
    st.error(f"{ETIQUETA}: los resultados de esta pestaña son hipotéticos. No modifican datos, tasas ni archivos.")
    c1, c2 = st.columns(2)
    mxn = c1.slider("Tasa MXN: variación (%)", -float(MAX_PCT), float(MAX_PCT), 0.0, 0.5, key="sim_mxn")
    gtq = c2.slider("Tasa GTQ: variación (%)", -float(MAX_PCT), float(MAX_PCT), 0.0, 0.5, key="sim_gtq")
    sim = _simular(str(data_dir), str(profiles_dir or ""), mxn, gtq)
    cmp = compare(res, sim, periodo, {"MXN": Decimal(str(mxn)), "GTQ": Decimal(str(gtq))})
    st.caption(f"Período {periodo}. Una variación de +10 % significa que 1 unidad de esa moneda vale 10 % más "
               f"dólares. Las demás monedas no cambian.")

    def tabla(rows, fmt):
        return pd.DataFrame([{"Concepto": r.label, "Original": fmt(r.original), f"{ETIQUETA}": fmt(r.simulated),
                              "Diferencia": ("n/c" if r.difference is None else
                                             (fmt(r.difference) if fmt is _p else f"{r.difference:+,.2f}"))}
                             for r in rows])
    st.markdown("**Consolidado en USD**")
    st.dataframe(tabla(cmp.summary, _m), width="stretch", hide_index=True)
    st.markdown("**Indicadores (mensuales; WACC, impuesto y capital son SUPUESTO)**")
    filas = []
    for r in cmp.indicators:
        pct = r.label.startswith(("ROIC", "ROCE"))
        f = _p if pct else _m
        filas.append({"Indicador": r.label, "Original": f(r.original), ETIQUETA: f(r.simulated),
                      "Diferencia": "n/c" if r.difference is None else
                      (f"{r.difference:+.2%}" if pct else f"{r.difference:+,.2f}")})
    st.dataframe(pd.DataFrame(filas), width="stretch", hide_index=True)
    if cmp.open_ic_simulated != cmp.open_ic_original:
        st.warning(f"Con estas tasas, las operaciones intercompañía sin conciliar pasan de {cmp.open_ic_original} a "
                   f"{cmp.open_ic_simulated}: lo que dejaría de eliminarse automáticamente.")
    if mxn == 0 and gtq == 0:
        st.info("Mueve los controles para ver el efecto. Con 0 % la simulación es igual al original.")
