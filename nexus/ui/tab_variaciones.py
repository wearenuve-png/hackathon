"""Pestana de variaciones: explica por que cambia cada cifra entre dos periodos (plantillas, sin IA).

    from nexus.ui.tab_variaciones import render
    render(consolidado_actual, consolidado_previo)

Ambos son ConsolidatedView (nexus.variance.view(run, periodo)). La pestana no calcula nada: muestra el
VarianceReport de nexus.variance.compare con la frase para el director, la tabla de causas (que suman exacto el
total, o muestran 'Sin explicar') y la trazabilidad (archivo, hoja, fila, tasa, regla).
"""
from decimal import Decimal
from typing import Optional

import pandas as pd
import streamlit as st

from ..schemas import BLOCK
from ..variance import CAUSE_NAMES, CAUSES, SIN, compare, fmt, sfmt


def _pct(v) -> str:
    return "nueva" if v.pct is None else f"{v.pct:+.1%}"


def _causes_table(v) -> pd.DataFrame:
    rows = [{"Causa": CAUSE_NAMES[k], "USD": sfmt(x)} for k, x in v.causes.items() if x != 0 or k == SIN]
    rows.append({"Causa": "TOTAL (suma de causas + sin explicar)", "USD": sfmt(v.causes_sum)})
    return pd.DataFrame(rows)


def _trace_table(v) -> pd.DataFrame:
    return pd.DataFrame([{"Periodo": t.period, "Empresa": t.company_id, "Archivo": t.file, "Hoja": t.sheet or "-",
                          "Fila": t.row, "Cuenta local": t.account_local,
                          "Importe original": "n/c" if t.local is None else fmt(t.local), "Moneda": t.currency or "",
                          "Tasa": "" if t.rate is None else str(t.rate),
                          "USD": "n/c" if t.usd is None else fmt(t.usd), "Estado": t.status, "Regla / motivo": t.rule}
                         for t in v.trace])


def _show(v, expanded=False):
    etiquetas = " ".join(f"`{t}`" for t in v.tags)
    st.markdown(v.phrase)
    if etiquetas:
        st.caption(f"Etiquetas: {etiquetas}")
    st.dataframe(_causes_table(v), width="stretch", hide_index=True)
    for n in v.notes:
        st.warning(n)
    if v.trace:
        with st.expander(f"Trazabilidad ({len(v.trace)} registros)", expanded=expanded):
            st.dataframe(_trace_table(v), width="stretch", hide_index=True)


def render(consolidado_actual, consolidado_previo, params=None) -> None:
    st.subheader("Variaciones: ¿por qué cambió cada cifra?")
    if consolidado_previo is None:
        st.info("Este es el primer periodo: no hay periodo previo con el cual comparar.")
        return
    rep = compare(consolidado_previo, consolidado_actual, params=params)
    for f in rep.findings:
        (st.error if f.severity == BLOCK else st.warning)(f"[{f.rule_id}] {f.message}. {f.suggestion}")
    if rep.blocked:
        st.error("El umbral no es valido: no se calcula ninguna variacion hasta corregir config/variance.json.")
        return
    p0, p1 = rep.prev_period, rep.cur_period
    if rep.provisional:
        st.error("PROVISIONAL: al menos uno de los dos periodos lo es; las explicaciones heredan esa condicion.")
    st.caption(f"Comparacion {p0} → {p1}. Umbral de materialidad (SUPUESTO, config/variance.json): "
               f"{rep.params.min_pct:.0%} y {fmt(rep.params.min_abs_usd)} USD. {rep.convention}")

    st.info("Operación se mide sobre todo lo cargado y valorable, incluidos registros bloqueados; su exclusión aparece "
            "en «Ajustes y registros bloqueados». Un signo invertido se ve como movimiento grande en Operación "
            "compensado en esa causa.")
    st.markdown("### Utilidad neta consolidada")
    _show(rep.total, expanded=False)

    st.markdown("### Variaciones materiales por cuenta")
    mats = sorted((v for v in rep.by_account.values() if v.material), key=lambda v: -abs(v.total))
    if not mats:
        st.info("Ninguna cuenta supera el umbral.")
    else:
        st.dataframe(pd.DataFrame([{"Cuenta": v.label, "Previo": fmt(v.prev), "Actual": fmt(v.cur),
                                    "Variacion": sfmt(v.total), "%": _pct(v), "Sin explicar": sfmt(v.causes[SIN]),
                                    "Etiquetas": ", ".join(v.tags)} for v in mats]),
                     width="stretch", hide_index=True)
        for v in mats:
            with st.expander(f"{v.label}: {sfmt(v.total)} USD ({_pct(v)})"):
                _show(v)

    st.markdown("### Efecto en la utilidad neta por empresa")
    st.dataframe(pd.DataFrame([{"Empresa": v.label, "Previo": fmt(v.prev), "Actual": fmt(v.cur),
                                "Variacion": sfmt(v.total), "%": _pct(v), "Sin explicar": sfmt(v.causes[SIN]),
                                "Material": "si" if v.material else "no"} for v in rep.by_company.values()]),
                 width="stretch", hide_index=True)
    with st.expander("Detalle por empresa"):
        for v in rep.by_company.values():
            st.markdown(f"**{v.label}**")
            _show(v)

    if rep.outside:
        with st.expander(f"Registros fuera del consolidado en estos periodos ({len(rep.outside)})"):
            for line in rep.outside:
                st.text(line)
