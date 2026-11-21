"""Pestana de indicadores (ROIC, ROCE, EVA) para la interfaz.

    from nexus.ui.tab_indicadores import render
    render(consolidado, periodo)          # dentro de un st.tab / contenedor de Streamlit

`consolidado` es el RunResult del motor (nexus.pipeline.run). La pestana no calcula nada: llama a
nexus.metrics.compute_indicators y muestra formula, entradas usadas y resultado. Los parametros
(WACC, tasa de impuesto, capital) son SUPUESTOS editables y se marcan como tales.
"""
from decimal import Decimal
from typing import Optional

import pandas as pd
import streamlit as st

from ..metrics import CONSOLIDADO, SUPUESTO, IndicatorParams, compute_indicators, load_params
from ..schemas import BLOCK

PREFIX = "ind_"


def _m(d: Optional[Decimal]) -> str:
    return "n/c" if d is None else f"{d:,.2f}"


def _p(d: Optional[Decimal]) -> str:
    return "n/c" if d is None else f"{d:.2%}"


def _params_from_widgets(base: IndicatorParams, periodo: str) -> IndicatorParams:
    with st.expander("Supuestos (editables) - SUPUESTO, no son datos del reto", expanded=False):
        c1, c2, c3 = st.columns(3)
        wacc = c1.number_input("WACC anual (%)", value=float(base.wacc * 100), step=0.5, format="%.2f",
                               key=f"{PREFIX}wacc_{periodo}")
        tax = c2.number_input("Tasa de impuesto (%)", value=float(base.tax_rate * 100), step=1.0, format="%.2f",
                              key=f"{PREFIX}tax_{periodo}")
        opts = [12, 4, 2, 1]
        ppy = c3.selectbox("Periodos por anio", opts, index=opts.index(base.periods_per_year)
                           if base.periods_per_year in opts else 0, key=f"{PREFIX}ppy_{periodo}")
        fix = st.checkbox("Fijar el capital invertido a mano (en vez de deuda + patrimonio - caja)",
                          key=f"{PREFIX}fix_{periodo}")
        ci = None
        if fix:
            ci = Decimal(str(st.number_input("Capital invertido (USD)", value=0.0, step=1000.0,
                                             key=f"{PREFIX}ci_{periodo}")))
    return IndicatorParams(wacc=Decimal(str(wacc)) / 100, tax_rate=Decimal(str(tax)) / 100, periods_per_year=ppy,
                           cash_account_codes=base.cash_account_codes, invested_capital_override=ci,
                           capital_employed_override=base.capital_employed_override)


def render(consolidado, periodo: str, params: Optional[IndicatorParams] = None) -> None:
    st.subheader(f"Indicadores de rentabilidad - {periodo}")
    if params is None:
        params = _params_from_widgets(load_params(), periodo)
    r = compute_indicators(consolidado, periodo, params)

    if r.provisional:
        st.error("PROVISIONAL: el consolidado de este periodo lo es, y los indicadores heredan esa condicion.")
    st.warning("WACC, tasa de impuesto y la definicion de capital son **SUPUESTO** del equipo, no datos del reto. "
               "Los resultados son del periodo (no anualizados) salvo que diga lo contrario.")
    for f in r.findings:
        (st.error if f.severity == BLOCK else st.warning)(f"[{f.rule_id}] {f.message}. {f.suggestion}")

    ppy = params.periods_per_year
    c1, c2, c3 = st.columns(3)
    c1.metric("ROIC (mensual)", _p(r.roic))
    c2.metric("ROCE (mensual)", _p(r.roce))
    c3.metric("EVA (mensual, USD)", _m(r.eva))
    st.caption(f"(*) Anualizados serian ROIC {_p(r.roic_annualized)} y ROCE {_p(r.roce_annualized)}; no son "
               f"representativos por ser datos sinteticos.")

    st.markdown("**Formula y calculo con las entradas usadas**")
    w = params.wacc / ppy if ppy in (1, 2, 4, 12) else None
    rows = [
        ("NOPAT", r.formulas["NOPAT"],
         f"{_m(r.ebit)} x (1 - {params.tax_rate:.2%}) = {_m(r.nopat)}", _m(r.nopat)),
        ("ROIC", r.formulas["ROIC"],
         f"{_m(r.nopat)} / {_m(r.invested_capital)}", _p(r.roic)),
        ("ROCE", r.formulas["ROCE"],
         f"{_m(r.ebit)} / {_m(r.capital_employed)}", _p(r.roce)),
        ("EVA", r.formulas["EVA"],
         f"{_m(r.nopat)} - ({_p(params.wacc)} / {ppy}) x {_m(r.invested_capital)}"
         if w is not None else "n/c", _m(r.eva)),
    ]
    st.dataframe(pd.DataFrame([{"Indicador": a, "Formula": b, "Con las entradas": c, "Resultado": d}
                               for a, b, c, d in rows]), width="stretch", hide_index=True)

    st.markdown("**Entradas usadas y de donde vienen**")
    st.dataframe(pd.DataFrame([{"Entrada": i.name, "Valor": _m(i.value), "Origen": i.source, "Nota": i.note}
                               for i in r.inputs]), width="stretch", hide_index=True)
    st.caption(f"{r.formulas['CI']}. {r.formulas['CE']}. Origen {CONSOLIDADO} = cifra del consolidado en USD; "
               f"origen {SUPUESTO} = decision del equipo.")
