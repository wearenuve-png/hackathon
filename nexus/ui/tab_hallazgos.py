"""Pestana Hallazgos: una ficha por hallazgo, con contador por tipo y orden por impacto (sin IA).

    from nexus.ui.tab_hallazgos import render
    render(consolidado, periodo)        # consolidado = RunResult
"""
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pandas as pd
import streamlit as st

from .. import diagnostico as DG
from ..diagnostico import NOMBRES, contador_por_tipo, diagnosticar, fmt
from . import correcciones as CO


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


@dataclass
class Contexto:
    """Lo que necesita la pestana para aprobar o rechazar correcciones (lo arma app.py)."""
    log_path: Path
    escenario: str
    bump: Callable[[], None]            # invalida el calculo para que se recalcule con las decisiones nuevas


TITULO_KIND = {CO.IMPORTE: "Importe corregido", CO.SIGNO: "Signo corregido", CO.TASA: "Tasa corregida",
               CO.MONEDA_ARCHIVO: "Moneda del archivo corregida", CO.ASIENTO: "Asiento agregado",
               CO.DUPLICADO: "Exclusión automática revertida"}


def _ids(f):
    return {f"{u.company_id}|{u.file}|{u.sheet or ''}|{u.row}" for u in f.donde}


def emparejar(fichas, props):
    """ficha_id -> propuesta (misma regla, empresa, periodo y registros)."""
    out, usados = {}, set()
    for f in fichas:
        for p in props:
            if p.key in usados or p.rule_id != f.rule_id or p.company_id != f.company_id or p.period != f.period:
                continue
            if p.record_ids and not set(p.record_ids) <= _ids(f):
                continue
            out[f.ficha_id] = p
            usados.add(p.key)
            break
    return out


def cascada(fichas, props_por_ficha):
    """Hallazgos que son CONSECUENCIA de otro (p. ej. 28 importes atipicos por una tasa mal escrita): ficha_id -> padre."""
    hijos = {}
    for pid, p in props_por_ficha.items():
        for f in fichas:
            if f.ficha_id == pid or f.ficha_id in hijos:
                continue
            if p.kind == CO.TASA and f.period == p.period and f.tipo in (DG.MONEDA_SOSPECHOSA, DG.IMPORTE_ATIPICO) \
                    and f.donde and all(u.moneda == p.extra["moneda"] for u in f.donde):
                hijos[f.ficha_id] = pid
            elif p.kind == CO.MONEDA_ARCHIVO and f.company_id == p.company_id and f.tipo in (DG.MES_FALTANTE,
                                                                                            DG.INTERCOMPANIA):
                hijos[f.ficha_id] = pid
    return hijos


def _decidir(p, evento, ctx, cuenta_key=None):
    quien = (st.session_state.get("aprobador") or "").strip()
    cuenta = st.session_state.get(cuenta_key) if cuenta_key else None
    CO.registrar(ctx.log_path, CO.evento_desde(p, evento, quien, ctx.escenario, cuenta))
    ctx.bump()


def _deshacer(ev, ctx):
    CO.registrar(ctx.log_path, {"evento": "DESHACER", "quien": (st.session_state.get("aprobador") or "").strip(),
                                "escenario": ctx.escenario, "key": ev["key"], "kind": ev["kind"],
                                "valor_leido": ev.get("valor_leido"), "valor_propuesto": ev.get("valor_propuesto"),
                                "motivo": "Se deshizo la decisión anterior"})
    ctx.bump()


def _bloque_decision(f, p, ctx, quien):
    """Lo que NEXUS hizo, que propone y que debe decidir una persona + botones."""
    st.markdown(f"**Valor leído.** `{p.valor_leido}`")
    st.markdown(f"**Qué hizo NEXUS.** {p.que_hizo}")
    if p.accion == CO.AUTO:
        st.markdown(f"**Acción.** APLICADA AUTOMÁTICAMENTE (solo el duplicado exacto con el mismo ID). {p.motivo}")
    else:
        prop = "-" if p.valor_propuesto is None else p.valor_propuesto
        if p.estimacion:
            st.warning(CO.ESTIMACION, icon=":material/functions:")
        st.markdown(f"**Qué propone.** {p.motivo} Valor propuesto: **{prop}**. Impacto en USD: "
                    f"**{fmt(p.impacto_usd)}**. {p.impacto_utilidad}")
    st.markdown(f"**Qué debe decidir una persona.** {p.decide}")
    if p.accion == CO.AUTO:
        st.button("Revertir exclusión automática", key=f"revertir_{p.key}", on_click=_decidir,
                  args=(p, "APROBAR", ctx))
        return
    if not p.aprobable:
        return
    cuenta_key = None
    if p.cuenta_requerida:
        cuenta_key = f"cuenta_{p.key}"
        nombres = dict(p.extra["opciones"])
        st.selectbox("Cuenta del asiento omitido", [None] + list(nombres), key=cuenta_key,
                     format_func=lambda c: "— elige una cuenta —" if c is None else f"{c} - {nombres[c]}")
    falta_cuenta = p.cuenta_requerida and not st.session_state.get(cuenta_key)
    c1, c2 = st.columns(2)
    c1.button("Aprobar corrección", key=f"aprobar_{p.key}", on_click=_decidir, args=(p, "APROBAR", ctx, cuenta_key),
              disabled=not quien or falta_cuenta, type="primary")
    c2.button("Rechazar", key=f"rechazar_{p.key}", on_click=_decidir, args=(p, "RECHAZAR", ctx))
    if not quien:
        st.caption("Escribe tu nombre arriba («Quién aprueba») para habilitar «Aprobar corrección».")


def _resueltos(est, ctx):
    ap = [e for e in est.values() if e["evento"] == "APROBAR"]
    re_ = [e for e in est.values() if e["evento"] == "RECHAZAR"]
    if ap:
        st.markdown("### Resueltos")
        for e in ap:
            with st.expander(f"✔ Resuelto · {TITULO_KIND.get(e['kind'], e['kind'])} · {e.get('company_id') or 'Grupo'}"
                             f" · {e.get('period') or '-'}"):
                st.markdown(f"Aprobado por **{e['quien']}** el {e['ts']}. Valor leído `{e['valor_leido']}` → valor "
                            f"aprobado `{e['valor_propuesto']}`{' en la cuenta ' + e['cuenta'] if e.get('cuenta') else ''}. "
                            f"{e['motivo']}")
                st.caption("El archivo fuente no se modificó: la corrección se aplica en el cálculo y queda en el "
                           "registro de auditoría.")
                st.button("Deshacer", key=f"deshacer_{e['key']}", on_click=_deshacer, args=(e, ctx))
    if re_:
        st.markdown("### Rechazadas (siguen abiertas)")
        for e in re_:
            with st.expander(f"✖ Rechazada · {TITULO_KIND.get(e['kind'], e['kind'])} · {e.get('company_id') or 'Grupo'}"):
                st.markdown(f"Rechazada por **{e['quien'] or 'sin nombre'}** el {e['ts']}. El hallazgo sigue abierto: "
                            f"hay que corregir el archivo de origen.")
                st.button("Deshacer rechazo", key=f"deshacer_{e['key']}", on_click=_deshacer, args=(e, ctx))


def render(consolidado, periodo=None, contexto=None) -> None:
    st.subheader("Hallazgos: qué pasó, dónde, por qué importa y qué hacer")
    fichas = [f for f in diagnosticar(consolidado) if periodo is None or f.period in (None, periodo)]
    if contexto is not None:
        return _render_con_decisiones(consolidado, periodo, fichas, contexto)
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


def _render_con_decisiones(res, periodo, fichas, ctx) -> None:
    props = CO.proponer(res)
    est = CO.estado(ctx.log_path, ctx.escenario)
    pares = emparejar(fichas, props)
    hijos = cascada(fichas, pares)
    if not st.session_state.get("aprobador"):
        st.session_state["aprobador"] = os.environ.get("NEXUS_APROBADOR", "")
    st.text_input("Quién aprueba (tu nombre)", key="aprobador",
                  help="Queda en el registro de auditoría junto con la fecha, el valor y el motivo.")
    quien = (st.session_state.get("aprobador") or "").strip()
    st.caption("Plantillas en español, sin IA. La causa siempre es **probable** y la decisión es de una persona: NEXUS "
               "no corrige ni convierte nada por su cuenta, y el archivo fuente NUNCA se modifica.")
    visibles = [f for f in fichas if f.ficha_id not in hijos]
    rechazadas = {p.key for p in props if est.get(p.key, {}).get("evento") == "RECHAZAR"}
    pendientes = [f for f in visibles if f.ficha_id in pares and pares[f.ficha_id].aprobable
                  and pares[f.ficha_id].key not in rechazadas]
    autom = [f for f in visibles if f.ficha_id in pares and pares[f.ficha_id].accion == CO.AUTO]
    resto = [f for f in visibles if f not in pendientes and f not in autom]
    n_res = sum(1 for e in est.values() if e["evento"] == "APROBAR")
    c = st.columns(4)
    c[0].metric("Pendientes de tu decisión", len(pendientes))
    c[1].metric("Aplicadas automáticamente", len(autom))
    c[2].metric("Resueltos", n_res)
    c[3].metric("Rechazadas", len(rechazadas))
    if not fichas:
        st.success("Sin hallazgos en este período.")
    else:
        cont = contador_por_tipo(visibles)
        if cont:
            cols = st.columns(min(4, len(cont)))
            for i, (tipo, n) in enumerate(cont.items()):
                cols[i % len(cols)].metric(NOMBRES[tipo], n)
        st.caption(f"{len(visibles)} hallazgo(s) a la vista" + (f"; {len(hijos)} más son consecuencia de otro y están "
                   f"dentro de su ficha." if hijos else "") + ". Orden: pendientes de decisión primero.")
    for titulo, grupo in (("Pendientes de tu decisión", pendientes), ("Aplicadas automáticamente", autom),
                          ("Otros hallazgos", resto)):
        if not grupo:
            continue
        st.markdown(f"### {titulo}")
        for f in grupo:
            p = pares.get(f.ficha_id)
            etiqueta = (f"{f.ficha_id} · {NOMBRES[f.tipo]} · {f.company_id or '-'} · {f.period or '-'} · "
                        f"{'n/c' if f.impacto_usd is None else fmt(f.impacto_usd) + ' USD'}")
            with st.expander(etiqueta):
                _ficha(f)
                if p is not None:
                    _bloque_decision(f, p, ctx, quien)
                mios = [h for h in fichas if hijos.get(h.ficha_id) == f.ficha_id]
                if mios:
                    with st.expander(f"Consecuencias de este hallazgo ({len(mios)}): se resuelven al resolverlo"):
                        for h in mios:
                            st.markdown(f"- {NOMBRES[h.tipo]} · {h.company_id or '-'} · {h.que_paso}")
    _resueltos(est, ctx)
