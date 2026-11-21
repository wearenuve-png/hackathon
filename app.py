"""NEXUS - interfaz Streamlit.

La interfaz NO calcula cifras del consolidado: solo ordena y muestra lo que devuelve el motor
(nexus.pipeline.run). Las secciones se eligen en el menu horizontal de arriba (key "nav") y el modo
claro/oscuro con el boton de luna/sol de la barra lateral (key "tema").
Hallazgos (con fichas y aprobacion humana), Indicadores, Variaciones, Simulador, Ayuda, Asistente y Seguridad e
integridad viven en nexus/ui/ y asistente/. El escenario (datos base o demostracion con errores) se elige arriba.

Ejecutar:  streamlit run app.py
"""
import json
import sys
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import altair as alt  # ya viene con streamlit (no es una dependencia nueva)
import pandas as pd
import streamlit as st
from streamlit import config as st_config

from nexus.audit import verify_hashes
from nexus.consolidation import trace
from nexus.pipeline import run
from nexus.schemas import BLOCK, BLOCKED, EXCLUDED_DUPLICATE, INFO, PENDING_MAPPING, WARN
from nexus.ui.colores import company_colors
from nexus.ui import (correcciones, explicar, extras, panel_seguridad, resumen_carga, tab_ayuda, tab_hallazgos,
                      tab_indicadores, tab_simulador, tab_variaciones)
from nexus.variance import view

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title="NEXUS | Consolidación", layout="wide", initial_sidebar_state="expanded")

# ------------------------------------------------------------------ temas (sin fuentes externas: corre sin red)
# Linea grafica del pitch: carbon, naranja NEXUS y blanco hueso; en modo claro, papel y tinta negra.
# El texto es blanco en oscuro y negro en claro: el color queda para puntos de estado, marca y graficos.
# Streamlit no cambia de tema desde el codigo: se ajustan sus opciones y se vuelve a dibujar la pagina.
THEMES = {
    "dark": {"theme.base": "dark", "theme.primaryColor": "#F05A28", "theme.backgroundColor": "#181716",
             "theme.secondaryBackgroundColor": "#23211F", "theme.textColor": "#F5F3EF", "theme.linkColor": "#F05A28",
             "theme.borderColor": "#3B3835", "theme.dataframeBorderColor": "#3B3835",
             "theme.dataframeHeaderBackgroundColor": "#23211F", "theme.redColor": "#FF5C93",
             "theme.greenColor": "#3DD68C", "theme.yellowColor": "#F7C948", "theme.orangeColor": "#F05A28",
             "theme.sidebar.backgroundColor": "#121110", "theme.sidebar.secondaryBackgroundColor": "#23211F"},
    "light": {"theme.base": "light", "theme.primaryColor": "#D9480F", "theme.backgroundColor": "#F6F5F2",
              "theme.secondaryBackgroundColor": "#ECE9E4", "theme.textColor": "#141312", "theme.linkColor": "#C2410C",
              "theme.borderColor": "#DAD5CD", "theme.dataframeBorderColor": "#DAD5CD",
              "theme.dataframeHeaderBackgroundColor": "#ECE9E4", "theme.redColor": "#D61F5B",
              "theme.greenColor": "#13894A", "theme.yellowColor": "#C98A00", "theme.orangeColor": "#D9480F",
              "theme.sidebar.backgroundColor": "#FFFFFF", "theme.sidebar.secondaryBackgroundColor": "#F1EEE9"},
}
TOKENS = {
    "dark": {"bg": "#181716", "panel": "#23211F", "line": "#3B3835", "ink": "#F5F3EF", "muted": "#CFCAC3",
             "brand": "#F05A28", "red": "#FF5C93", "amber": "#F7C948", "green": "#3DD68C"},
    "light": {"bg": "#F6F5F2", "panel": "#FFFFFF", "line": "#DAD5CD", "ink": "#141312", "muted": "#45413D",
              "brand": "#D9480F", "red": "#D61F5B", "amber": "#C98A00", "green": "#13894A"},
}
CSS = """
.block-container{padding-top:1.4rem;padding-left:2.2rem;padding-right:2.2rem;max-width:1420px}
[data-testid="stAppDeployButton"],.stDeployButton{display:none}
.nx-word{font-family:var(--display);font-weight:900;font-size:2.7rem;color:var(--brand);letter-spacing:-.055em;
 line-height:.95;margin:.1rem 0 .35rem}
.nx-word-sub{font-family:var(--display);font-weight:900;font-size:1.02rem;color:var(--ink);letter-spacing:-.02em;
 line-height:1.15;margin-bottom:1rem}
.nx-crew{font-size:.75rem;color:var(--muted);margin-top:.8rem}
.nx-title{font-family:var(--display);font-weight:900;font-size:2.15rem;color:var(--ink);letter-spacing:-.035em;
 line-height:1.05;margin:0}
.nx-section{font-size:1.25rem;font-weight:700;color:var(--ink);margin:.2rem 0 .8rem;padding-bottom:.45rem;
 border-bottom:2px solid var(--brand);display:inline-block}
.nx-lede{color:var(--muted);font-size:.95rem;margin:.4rem 0 .9rem}
.nx-wrap{container-type:inline-size}
.nx-strip{display:grid;grid-template-columns:repeat(var(--cols),minmax(0,1fr));gap:1px;background:var(--line);
 border:1px solid var(--line);border-radius:6px;overflow:hidden;margin:.2rem 0 1.2rem}
@container (max-width:760px){.nx-strip.c4{--cols:2}}
@container (max-width:520px){.nx-strip{--cols:1!important}}
.nx-fig{background:var(--panel);padding:12px 16px;min-width:0}
.nx-fig-l{font-size:.82rem;color:var(--muted)}
.nx-fig-v{font-size:1.5rem;font-weight:700;color:var(--ink);font-variant-numeric:tabular-nums;
 margin:2px 0 3px;overflow-wrap:anywhere}
.nx-fig-v.red::before,.nx-fig-v.amber::before,.nx-ok::before{content:"";display:inline-block;width:10px;height:10px;
 border-radius:50%;margin-right:8px;vertical-align:middle}
.nx-fig-v.red::before{background:var(--red)} .nx-fig-v.amber::before{background:var(--amber)}
.nx-ok::before{background:var(--green);width:8px;height:8px}
.nx-fig-n{font-size:.8rem;color:var(--muted);line-height:1.4}
.nx-h{font-size:1rem;font-weight:700;color:var(--ink);margin:.2rem 0 .5rem}
.nx-list{background:var(--panel);border:1px solid var(--line);border-radius:6px}
.nx-row{display:grid;grid-template-columns:10px 1fr auto;gap:10px;align-items:baseline;padding:9px 12px;
 border-top:1px solid var(--line)}
.nx-row:first-child{border-top:0}
.nx-dot{width:9px;height:9px;border-radius:50%;display:inline-block}
.nx-dot.green{background:var(--green)}.nx-dot.amber{background:var(--amber)}.nx-dot.red{background:var(--red)}
.nx-row-t{font-weight:600;color:var(--ink);font-size:.92rem}
.nx-row-s{color:var(--muted);font-size:.8rem;line-height:1.35}
.nx-state{font-size:.82rem;font-weight:700;color:var(--ink)}
.nx-ok{color:var(--ink);font-size:.85rem}
[data-testid="stAlertContainer"] [data-testid="stMarkdownContainer"] *{color:var(--ink)!important}
.st-key-nx_badge [data-testid="stAlertContainer"]{padding:.45rem .8rem}
.st-key-tema button{color:var(--ink)!important;background:transparent!important;border:0!important;padding:4px}
.st-key-tema button:hover,.st-key-tema button:focus{color:var(--ink)!important;opacity:.7}
.st-key-tema button span{font-size:1.6rem!important;color:var(--ink)!important}
.st-key-nx_badge p{white-space:nowrap;font-weight:600;letter-spacing:.03em;font-size:.88rem}
section[data-testid="stSidebar"] [data-testid="stAlertContainer"]{padding:.5rem .75rem}
.st-key-nav{margin-bottom:.6rem}
.st-key-nav [role="radiogroup"]{gap:0;flex-wrap:wrap;border-bottom:1px solid var(--line)}
.st-key-nav label[data-baseweb="radio"]{margin:0;padding:8px 6px 9px;border-bottom:3px solid transparent;
 border-radius:6px 6px 0 0;cursor:pointer}
.st-key-nav label[data-baseweb="radio"]>div:first-child{display:none}
.st-key-nav label[data-baseweb="radio"]:hover{background:var(--panel)}
.st-key-nav label[data-baseweb="radio"]:has(input:checked){border-bottom-color:var(--brand);background:var(--panel)}
.st-key-nav label[data-baseweb="radio"] p{font-weight:600;color:var(--ink);font-size:.86rem;white-space:nowrap}
"""

MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
          "noviembre", "diciembre"]
KIND = {"real": "cifras reales", "presupuesto": "presupuesto"}
SECTIONS = ["Inicio", "Estados financieros", "Alertas y errores", "Hallazgos", "Intercompañía",
            "Trazabilidad", "Indicadores", "Variaciones", "Simulador", "Perfiles e integridad", "Ayuda", "Asistente"]
NAV_LABEL = {"Inicio": ":material/home: Inicio", "Estados financieros": ":material/account_balance: Estados",
             "Alertas y errores": ":material/warning: Alertas", "Hallazgos": ":material/search: Hallazgos",
             "Intercompañía": ":material/sync_alt: Intercompañía", "Trazabilidad": ":material/account_tree: Trazabilidad",
             "Indicadores": ":material/monitoring: Indicadores", "Variaciones": ":material/query_stats: Variaciones",
             "Simulador": ":material/tune: Simulador", "Perfiles e integridad": ":material/verified_user: Integridad",
             "Ayuda": ":material/help: Ayuda", "Asistente": ":material/chat: Asistente"}
SEV_LABEL = {BLOCK: "Bloquea el cierre", WARN: "Revisar", INFO: "Nota"}
SEV_ORDER = {BLOCK: 0, WARN: 1, INFO: 2}
STATUS_LABEL = {BLOCKED: "Bloqueado", PENDING_MAPPING: "Cuenta sin confirmar", EXCLUDED_DUPLICATE: "Duplicado excluido"}
LOAD_LABEL = {"MATCHED": "Coincide con el perfil", "REVIEW": "EN REVISION (no coincide)", "AUTO": "Sin perfil (auto)"}


def m(d, plus=False):
    """Importe con separador de miles y 2 decimales (ROUND_HALF_UP)."""
    if d is None:
        return "n/c"
    s = f"{d.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):,.2f}"
    return ("+" + s) if plus and d > 0 else s


def pl(n, one, many):
    return f"{n} {one if n == 1 else many}"


def month(p):
    try:
        y, mo = p.split("-")
        return f"{MONTHS[int(mo) - 1]} {y}"
    except (ValueError, IndexError):
        return p


def html(s: str) -> None:
    st.markdown(s, unsafe_allow_html=True)


def figures(items):
    """Franja de cifras: [(etiqueta, valor, nota, tono)]."""
    cells = "".join(f'<div class="nx-fig"><div class="nx-fig-l">{escape(l)}</div>'
                    f'<div class="nx-fig-v {t}">{escape(str(v))}</div><div class="nx-fig-n">{escape(n)}</div></div>'
                    for l, v, n, t in items)
    html(f'<div class="nx-wrap"><div class="nx-strip c{len(items)}" style="--cols:{len(items)}">{cells}</div></div>')


def heading(text):
    html(f'<div class="nx-h">{escape(text)}</div>')


@st.cache_resource(show_spinner="Ejecutando el motor...")
def load(data_dir: str, profiles_dir: str, version: int):
    return run(data_dir, profiles_dir=profiles_dir or None)


@st.cache_resource(show_spinner="Recalculando con las correcciones aprobadas...")
def load_corregido(data_dir: str, profiles_dir: str, version: int, aprobadas: tuple):
    """Mismo motor, pero aplicando en memoria las correcciones aprobadas; los archivos no se modifican."""
    return correcciones.run_corregido(data_dir, profiles_dir or None, [json.loads(a) for a in aprobadas])


def group_ic(matches):
    """Una operacion entre empresas = (vendedor, comprador, referencia): la misma diferencia o eliminacion afecta a
    la operacion (venta) y al saldo (cuenta por cobrar y por pagar); se muestra una sola vez."""
    g = {}
    for x in matches:
        g.setdefault((x.seller_id, x.buyer_id, x.reference), []).append(x)
    return g


def afecta(xs):
    return " y ".join("operación (venta)" if y.statement == "ER" else "saldo (CxC y CxP)"
                      for y in sorted(xs, key=lambda y: y.statement != "ER"))


# ------------------------------------------------------------------ escenario (arriba, siempre visible)
ESCENARIOS = ["Datos base", "Datos con errores (demostración)"]


def _restablecer():
    """Vacia el registro de aprobaciones y vuelve al escenario base. No toca ningun archivo fuente."""
    correcciones.restablecer(correcciones.log_por_defecto())
    st.session_state["escenario"] = ESCENARIOS[0]
    st.session_state["ver"] = st.session_state.get("ver", 0) + 1
    st.session_state.pop("explicar_on", None)


_c_esc, _c_rst = st.columns([5, 1.3], vertical_alignment="bottom")
with _c_esc:
    escenario = st.radio("Escenario", ESCENARIOS, key="escenario", horizontal=True,
                         help="Ambos se leen en solo lectura. El segundo tiene 7 errores sembrados a propósito.")
with _c_rst:
    st.button("Restablecer demostración", key="restablecer_btn", on_click=_restablecer,
              help="Vacía el registro de aprobaciones y vuelve a «Datos base». No modifica ningún archivo.")
demo = escenario == ESCENARIOS[1]

# ------------------------------------------------------------------ barra lateral
if "modo_claro" not in st.session_state:
    st.session_state.modo_claro = False


def _cambiar_tema():
    st.session_state.modo_claro = not st.session_state.modo_claro


with st.sidebar:
    _logo, _tema = st.columns([4, 1], vertical_alignment="center")
    _logo.markdown('<div class="nx-word">NEXUS</div>', unsafe_allow_html=True)
    _claro = st.session_state.modo_claro                  # luna en oscuro, sol en claro; solo blanco y negro
    _tema.button("", key="tema", type="tertiary", on_click=_cambiar_tema,
                 icon=":material/light_mode:" if _claro else ":material/dark_mode:",
                 help="Cambiar a modo oscuro" if _claro else "Cambiar a modo claro")
    html('<div class="nx-word-sub">Muchas empresas.<br>Un solo número.</div>')
MODE = "light" if st.session_state.modo_claro else "dark"
if st_config.get_option("theme.base") != MODE:          # aplica el tema elegido y vuelve a dibujar
    for _k, _v in THEMES[MODE].items():
        st_config.set_option(_k, _v)
    st.rerun()
_t = TOKENS[MODE]
html("<style>:root{" + "".join(f"--{k}:{v};" for k, v in _t.items())
     + '--display:"Inter Display","Inter Tight","Segoe UI Black","Arial Black","Helvetica Neue",Arial,sans-serif;}'
     + CSS + "</style>")

with st.sidebar:
    period_box = st.container()
    status_box = st.container()
    with st.expander("Fuente de datos"):
        data_dir = st.text_input("Carpeta de archivos", str(ROOT / "data" / ("demo_errores" if demo else "synthetic")),
                                 key=f"data_dir_{int(demo)}")
        profiles_dir = st.text_input("Carpeta de perfiles",
                                     str(ROOT / "data" / "demo_errores" / "perfiles" if demo else ROOT / "profiles"),
                                     key=f"profiles_dir_{int(demo)}")
        if "ver" not in st.session_state:
            st.session_state.ver = 0
        if st.button("Volver a ejecutar"):
            st.session_state.ver += 1

LOG = correcciones.log_por_defecto()
_aprobadas = correcciones.aprobaciones(LOG, str(data_dir))
try:
    res = (load_corregido(data_dir, profiles_dir, st.session_state.ver,
                          tuple(json.dumps(a, sort_keys=True) for a in _aprobadas))
           if _aprobadas else load(data_dir, profiles_dir, st.session_state.ver))
except Exception as e:  # noqa: BLE001 - se muestra el error tal cual
    st.error(f"No se pudo ejecutar el motor: {e}")
    st.stop()

cfg = res.config
_dirs = [d for d in (data_dir, profiles_dir) if d]
_ver = verify_hashes(res.input_hashes, _dirs)
n_hash_ok = sum(1 for v in _ver.values() if v["status"] == "OK")
synthetic = "synthetic" in Path(data_dir).parts

with period_box:
    period = st.radio("Período", list(res.periods), format_func=lambda p: f"{p} ({res.periods[p].kind})")
with status_box:
    st.success("Fuente: carpeta del servidor (solo lectura)", icon=":material/folder_open:")
    if n_hash_ok == len(_ver):
        html(f'<div class="nx-ok">{n_hash_ok}/{len(_ver)} archivos íntegros</div>')
    else:
        st.error("Archivos modificados. Vuelve a ejecutar.")
    if synthetic:
        st.caption("Datos sintéticos")
with st.sidebar:
    extras.render_descarga(res, period, data_dir)
st.sidebar.markdown('<div class="nx-crew">Hecho por Cuz Cuz Crew</div>', unsafe_allow_html=True)

pr = res.periods[period]
s, n = pr.summary, pr.naive_summary
recs_by_id = {r.record_id: r for r in res.records}
adjs_by_id = {a.adjustment_id: a for a in res.adjustments}
ms = [x for x in res.matches if x.period == period]
ic_ok = [x for x in ms if x.status == "RECONCILED"]
ic_open = [x for x in ms if x.status != "RECONCILED"]
ic_ok_g, ic_groups = group_ic(ic_ok), group_ic(ic_open)
unresolved = [e for e in pr.excluded if e.status in (BLOCKED, PENDING_MAPPING)]
dups = [e for e in pr.excluded if e.status == EXCLUDED_DUPLICATE]
findings = sorted([f for f in res.findings if f.period in (None, period)],
                  key=lambda f: (SEV_ORDER.get(f.severity, 9), f.company_id or "", f.rule_id))
currencies = sorted({c.currency for c in cfg.companies.values()})

# ------------------------------------------------------------------ menu horizontal + encabezado
if demo:
    st.error("DEMOSTRACIÓN: datos de prueba con errores sembrados", icon=":material/science:")
section = st.radio("Sección", SECTIONS, key="nav", horizontal=True, label_visibility="collapsed",
                   format_func=lambda x: NAV_LABEL.get(x, x), width="stretch")
head, badge_col = st.columns([5, 1.1], vertical_alignment="center")
with head:
    html(f'<div class="nx-title">Consolidado de {escape(month(period))}</div>'
         f'<div class="nx-lede">{escape(KIND.get(pr.kind, pr.kind).capitalize())}, {len(cfg.companies)} empresas, '
         f'{len(currencies)} monedas, en USD</div>')
with badge_col.container(key="nx_badge"):
    if pr.provisional:
        st.error("PROVISIONAL", icon=":material/schedule:")
    else:
        st.success("COMPLETO", icon=":material/check_circle:")

elim_ing = s["ingresos"] - n["ingresos"]
figures([
    ("Ingresos (USD)", m(s["ingresos"]), f"Eliminado {m(elim_ing)}", ""),
    ("Utilidad neta (USD)", m(s["utilidad_neta"]),
     f"Rango {m(pr.utility_range[0])} a {m(pr.utility_range[1])}" if pr.utility_range else "Sin pendientes", ""),
    ("Registros bloqueados", len(unresolved), "Fuera del consolidado" if unresolved else "Sin bloqueos",
     "red" if unresolved else ""),
    ("Diferencias entre empresas", len(ic_groups), f"{len(ic_ok_g)} conciliadas", "amber" if ic_open else ""),
])

props_abiertas = correcciones.proponer(res)


# ------------------------------------------------------------------ Inicio (resumen del mes)
if section == "Inicio":
    heading("Resumen de la carga")
    resumen_carga.render(res, props_abiertas, demo=demo)
    explicar.render(res, period, props_abiertas)
    st.write("")
    left, right = st.columns([3, 2], gap="large")
    with left:
        heading("Ingresos por empresa (USD)")
        rev_codes = [c for c, a in cfg.catalog.items() if a.cls == "ingreso" and c in pr.lines]
        gross, elim = defaultdict(Decimal), defaultdict(Decimal)
        for c in rev_codes:
            for rid in pr.lines[c].record_ids:
                gross[recs_by_id[rid].company_id] += recs_by_id[rid].amount_usd
            for aid in pr.lines[c].adjustment_ids:
                a = adjs_by_id[aid]
                for rid in a.record_ids:
                    elim[recs_by_id[rid].company_id] += a.amount_usd
        # float solo para dibujar; las cifras auditables siguen en Decimal en las tablas
        colors = company_colors(cfg.companies, MODE)
        names = [cfg.companies[cid].name for cid in cfg.companies]
        parts = [("Queda en el consolidado", lambda cid: gross[cid] + elim[cid]),
                 ("Venta entre empresas del grupo (se elimina)", lambda cid: -elim[cid])]
        chart = pd.DataFrame([{"Empresa": cfg.companies[cid].name, "ID": cid, "Pais": cfg.companies[cid].country,
                               "Parte": lbl, "orden": i, "USD": float(fn(cid)), "Importe": f"{m(fn(cid))} USD",
                               "Reportado": f"{m(gross[cid])} USD"}
                              for cid in cfg.companies for i, (lbl, fn) in enumerate(parts)])
        if gross:
            # 2 px del color de fondo entre segmentos y extremos redondeados (guia de graficos del equipo)
            bars = alt.Chart(chart).mark_bar(stroke=_t["bg"], strokeWidth=2, cornerRadiusEnd=4).encode(
                y=alt.Y("Empresa:N", title=None, sort=None, axis=alt.Axis(labelLimit=220, labelFontSize=12)),
                x=alt.X("USD:Q", title=None, stack="zero", axis=alt.Axis(format=",.0f", grid=True, tickCount=5)),
                color=alt.Color("Empresa:N", legend=None,
                                scale=alt.Scale(domain=names, range=[colors[cid] for cid in cfg.companies])),
                opacity=alt.Opacity("Parte:N", title=None,
                                    scale=alt.Scale(domain=[p[0] for p in parts], range=[1.0, 0.35]),
                                    legend=alt.Legend(orient="bottom", direction="horizontal", labelLimit=420,
                                                      columns=1)),
                order=alt.Order("orden:Q"),
                tooltip=[alt.Tooltip("Empresa:N"), alt.Tooltip("ID:N"), alt.Tooltip("Pais:N", title="País"),
                         alt.Tooltip("Parte:N"), alt.Tooltip("Importe:N"),
                         alt.Tooltip("Reportado:N", title="Reportado por la empresa")],
            ).properties(height=44 * len(cfg.companies) + 40)
            st.altair_chart(bars, use_container_width=True)
            ok_tot = (sum(gross.values(), Decimal(0)) == n["ingresos"]
                      and sum(gross.values(), Decimal(0)) + sum(elim.values(), Decimal(0)) == s["ingresos"])
            st.caption("Parte clara: ventas entre empresas, eliminadas. "
                       + ("Cuadra con el estado de resultados." if ok_tot else "No cuadra con el estado de resultados."))
        else:
            st.info("No hay ingresos consolidados en este período.")

    with right:
        heading("Estado de cada empresa")
        rows = []
        for cid, c in cfg.companies.items():
            rep, prof = res.load_reports.get(cid), cfg.profiles.get(cid)
            f_c = [f for f in findings if f.company_id == cid]
            n_block = sum(1 for f in f_c if f.severity == BLOCK)
            n_warn = sum(1 for f in f_c if f.severity == WARN)
            n_out = sum(1 for e in unresolved if e.company_id == cid)
            n_dup = sum(1 for e in dups if e.company_id == cid)
            n_ic = sum(1 for k in ic_groups if cid in (k[0], k[1]))
            red, amber = [], []
            if rep is not None and rep.status == "REVIEW":
                red.append("archivo no coincide con su perfil")
            if cid in pr.missing_companies:
                red.append("sin datos del período")
            if n_out:
                red.append(pl(n_out, "registro bloqueado", "registros bloqueados"))
            if n_block and not n_out:
                red.append(pl(n_block, "alerta que bloquea", "alertas que bloquean"))
            if n_ic:
                amber.append(pl(n_ic, "diferencia entre empresas", "diferencias entre empresas"))
            if n_warn:
                amber.append(pl(n_warn, "advertencia", "advertencias"))
            if n_dup:
                amber.append(pl(n_dup, "duplicado excluido", "duplicados excluidos"))
            if prof is not None and prof.approval_status != "APPROVED":
                amber.append("perfil sin aprobar")
            tone = "red" if red else ("amber" if amber else "green")
            why = ", ".join(red + amber)
            label = {"red": "Bloqueada", "amber": "Revisar", "green": "Lista"}[tone]
            rows.append(f'<div class="nx-row"><span class="nx-dot {tone}"></span><div>'
                        f'<div class="nx-row-t">{escape(c.name)}</div>'
                        f'<div class="nx-row-s">{escape(cid)}, {escape(c.currency)}{": " + escape(why) if why else ""}'
                        f'</div></div>'
                        f'<span class="nx-state {tone}">{label}</span></div>')
        html('<div class="nx-list">' + "".join(rows) + "</div>")

    st.write("")
    a, b = st.columns(2, gap="large")
    with a:
        heading("Pendientes")
        if pr.provisional:
            with st.container(border=True):
                for why in pr.provisional_reasons:
                    st.markdown(f"- {why}")
                if pr.utility_range:
                    lo, hi = pr.utility_range
                    st.markdown(f"**Rango posible de utilidad neta:** {m(lo)} a {m(hi)} USD")
        else:
            st.success("Sin pendientes.")
    with b:
        heading("Prioridades")
        top = [f for f in findings if f.severity in (BLOCK, WARN)][:3]
        if top:
            with st.container(border=True):
                for f in top:
                    st.markdown(f"- **{f.company_id or 'Grupo'}**: {f.message}")
        else:
            st.caption("Sin prioridades.")
    st.write("")
    heading("Nivel de confianza")
    extras.render_confianza(res, period)

# ------------------------------------------------------------------ Estados financieros
if section == "Estados financieros":
    er, bg = st.columns([3, 2], gap="large")
    with er:
        heading("Estado de resultados (USD)")
        rows = [("Ingresos", "ingresos"), ("(-) Costo de ventas", "costo_ventas"),
                ("(-) Gastos operativos", "gastos_operativos"), ("= EBIT", "ebit"),
                ("(-) Gastos financieros", "gastos_financieros"), ("(-) Impuestos", "impuestos"),
                ("= Utilidad neta", "utilidad_neta")]
        st.dataframe(pd.DataFrame([{"Concepto": lbl, "Suma de empresas": m(n[k]),
                                    "Eliminaciones": m(s[k] - n[k], True), "Consolidado": m(s[k])}
                                   for lbl, k in rows]),
                     width="stretch", hide_index=True)
        st.caption("La utilidad no cambia al eliminar.")
    with bg:
        heading("Balance general (USD)")
        brow = [("Activo total", "activo_total"), ("Pasivo total", "pasivo_total"), ("Patrimonio", "patrimonio")]
        st.dataframe(pd.DataFrame([{"Concepto": lbl, "Suma de empresas": m(n[k]),
                                    "Eliminaciones": m(s[k] - n[k], True), "Consolidado": m(s[k])}
                                   for lbl, k in brow]),
                     width="stretch", hide_index=True)
        diff = s["activo_menos_pasivo_y_patrimonio"]
        (st.success if m(diff) == "0.00" else st.error)(f"Activo - (Pasivo + Patrimonio) = {m(diff)} USD")
    with st.expander("Detalle por cuenta"):
        st.dataframe(pd.DataFrame([{"Cuenta": c, "Nombre": cfg.catalog[c].name, "Antes de eliminar": m(ln.gross_usd),
                                    "Consolidado": m(ln.amount_usd)} for c, ln in pr.lines.items()]),
                     width="stretch", hide_index=True)

# ------------------------------------------------------------------ Alertas y errores
if section == "Alertas y errores":
    by_sev = defaultdict(int)
    for f in findings:
        by_sev[f.severity] += 1
    st.markdown(f"**{by_sev[BLOCK]}** bloquean el cierre, **{by_sev[WARN]}** por revisar, "
                f"**{by_sev[INFO]}** {'nota' if by_sev[INFO] == 1 else 'notas'}")
    if findings:
        st.dataframe(pd.DataFrame([{"Tipo": SEV_LABEL.get(f.severity, f.severity), "Empresa": f.company_id or "Grupo",
                                    "Qué pasó": f.message, "Qué hacer": f.suggestion, "Regla": f.rule_id}
                                   for f in findings]),
                     width="stretch", hide_index=True)
    else:
        st.info("Sin alertas en este período.")

    heading("Fuera del consolidado")
    if pr.excluded:
        st.dataframe(pd.DataFrame([{"Empresa": e.company_id, "Estado": STATUS_LABEL.get(e.status, e.status),
                                    "Motivo": "; ".join(e.reasons), "Importe original": m(e.amount_original),
                                    "Moneda": e.currency or "", "Importe USD": m(e.amount_usd),
                                    "Registro": e.record_id, "Código": e.status} for e in pr.excluded]),
                     width="stretch", hide_index=True)
        tot = ", ".join(f"{STATUS_LABEL.get(k, k).lower()} {m(v)} USD" for k, v in pr.excluded_usd_by_status.items())
        st.caption(f"Total: {tot or 'sin importes convertibles'}."
                   + (f" {pl(pr.excluded_not_convertible, 'registro no se pudo', 'registros no se pudieron')} "
                      f"convertir (n/c)." if pr.excluded_not_convertible else ""))
    else:
        st.info("Todo lo cargado entró al consolidado.")

    heading("Impacto en la utilidad")
    if pr.impact_ranges:
        st.dataframe(pd.DataFrame([{"Registro": i.record_id, "Empresa": i.company_id, "Excluido": m(i.utility_excluded),
                                    "Si entra como viene": m(i.utility_as_is, True),
                                    "Si se corrige": m(i.utility_corrected, True), "Nota": i.note}
                                   for i in pr.impact_ranges]),
                     width="stretch", hide_index=True)
    else:
        st.caption("Sin impacto en la utilidad.")

# ------------------------------------------------------------------ Intercompañía
if section == "Intercompañía":
    figures([
        ("Conciliadas", len(ic_ok_g), "Eliminadas", ""),
        ("Sin conciliar", len(ic_groups), "No se eliminan", "amber" if ic_open else ""),
        ("Tolerancia (USD)", m(cfg.ic_tolerance_usd), "Diferencia máxima", ""),
    ])
    heading("Sin conciliar")
    if ic_open:
        st.dataframe(pd.DataFrame([{"Vendedor": k[0], "Comprador": k[1], "Referencia": k[2],
                                    "Afecta": afecta(v),
                                    "USD vendedor": m(v[0].seller_usd), "USD comprador": m(v[0].buyer_usd),
                                    "Diferencia": m(v[0].difference_usd), "Estado": v[0].status}
                                   for k, v in ic_groups.items()]),
                     width="stretch", hide_index=True)
        st.caption("Cada discrepancia aparece una sola vez, aunque afecte venta y saldo.")
    else:
        st.success("Todo concilia.")
    with st.expander(f"Eliminadas ({len(ic_ok_g)})"):
        st.dataframe(pd.DataFrame([{"Vendedor": k[0], "Comprador": k[1], "Referencia": k[2], "Afecta": afecta(v),
                                    "USD vendedor": m(v[0].seller_usd), "USD comprador": m(v[0].buyer_usd)}
                                   for k, v in ic_ok_g.items()]),
                     width="stretch", hide_index=True)

# ------------------------------------------------------------------ Trazabilidad
if section == "Trazabilidad":
    groups = {"Ingresos": "ingreso", "Costo de ventas": "costo", "Gastos operativos": "gasto_operativo",
              "Gastos financieros": "gasto_financiero", "Impuestos": "impuesto", "Activo": "activo",
              "Pasivo": "pasivo", "Patrimonio": "patrimonio"}
    options = {f"{lbl} (total)": [c for c, a in cfg.catalog.items() if a.cls == cls] for lbl, cls in groups.items()}
    options.update({f"{cfg.catalog[c].name} (cuenta {c})": [c] for c in pr.lines})
    choice = st.selectbox("Cifra", list(options), key="traza_cifra")
    traces = [trace(period, c, res) for c in options[choice]]
    tr_gross = sum((t["gross_usd"] for t in traces), Decimal(0))
    tr_final = sum((t["amount_usd"] for t in traces), Decimal(0))
    figures([
        ("Reportado (USD)", m(tr_gross), "Suma de registros", ""),
        ("Eliminaciones (USD)", m(tr_final - tr_gross, True), "Entre empresas", ""),
        ("Consolidado (USD)", m(tr_final), "En estados financieros", ""),
    ])
    if len(options[choice]) == 1 and cfg.catalog[options[choice][0]].cls == "ingreso" and s["ingresos"] != tr_final:
        st.caption(f"Esta cifra es solo la cuenta {options[choice][0]}. Difiere del total de ingresos del consolidado "
                   f"({m(s['ingresos'])} USD) porque ese total incluye otras cuentas de ingresos.")
    recs = [{"Cuenta": t["account_code"], "Empresa": x["company_id"], "Archivo": x["file"],
             "Hoja": x["sheet"] or "-", "Fila": x["row"], "Cuenta local": x["account_local"],
             "Importe original": m(x["amount_original"]), "Moneda": x["currency"],
             "Tasa": str(x["fx_rate"]), "Orientacion": "multiplica (USD por unidad local)"
             if x["fx_orientation"] == "USD_PER_LOCAL" else "divide (local por USD)",
             "Importe USD": m(x["amount_usd"]), "Contraparte": x["counterparty_id"] or "",
             "ID transaccion": x["transaction_id"] or ""} for t in traces for x in t["records"]]
    heading(f"Filas de origen ({len(recs)})")
    st.dataframe(pd.DataFrame(recs), width="stretch", hide_index=True)
    adjs = [{"Ajuste": a["adjustment_id"], "Tipo": a["kind"], "USD": m(a["amount_usd"], True), "Regla": a["rule"],
             "Motivo": a["reason"]} for t in traces for a in t["adjustments"]]
    heading(f"Ajustes ({len(adjs)})")
    if adjs:
        st.dataframe(pd.DataFrame(adjs), width="stretch", hide_index=True)
    else:
        st.caption("Sin ajustes.")

# ------------------------------------------------------------------ secciones de otros integrantes
if section == "Hallazgos":
    tab_hallazgos.render(res, period, tab_hallazgos.Contexto(LOG, str(data_dir), lambda: st.session_state.update(
        ver=st.session_state.ver + 1)))
if section == "Indicadores":
    tab_indicadores.render(res, period)
if section == "Variaciones":
    _ps = sorted(res.periods)
    _i = _ps.index(period)
    tab_variaciones.render(view(res, period), view(res, _ps[_i - 1]) if _i > 0 else None)
if section == "Simulador":
    tab_simulador.render(res, period, data_dir, profiles_dir)
if section == "Ayuda":
    tab_ayuda.render()

# ------------------------------------------------------------------ Perfiles e integridad
if section == "Perfiles e integridad":
    heading("Perfiles por empresa")
    prof_rows = []
    for cid, c in cfg.companies.items():
        rep, p = res.load_reports.get(cid), cfg.profiles.get(cid)
        prof_rows.append({"Empresa": cid, "Nombre": c.name, "Moneda": c.currency,
                          "Formato": p.source.type.upper() if p else "-", "Archivo": c.file,
                          "Version": p.profile_version if p else "-",
                          "Aprobado por": (p.approved_by or "PENDIENTE") if p else "-",
                          "Ultima carga": LOAD_LABEL.get(rep.status, rep.status) if rep else "-",
                          "Registros": rep.n_records if rep else 0})
    st.dataframe(pd.DataFrame(prof_rows), width="stretch", hide_index=True)
    for r in [r for r in res.load_reports.values() if r.status == "REVIEW"]:
        st.error(f"{r.company_id} ({r.file}) quedó en revisión y no aporta registros:\n\n- " + "\n- ".join(r.reasons))
    for r in res.load_reports.values():
        for note in r.notes:
            st.warning(f"{r.company_id}: {note}")
    if not cfg.profiles:
        st.info("Sin perfiles: detección automática.")
    pend = [c for c, p in cfg.profiles.items() if p.approval_status != "APPROVED"]
    if pend:
        st.warning("Perfiles sin aprobar: " + ", ".join(pend))

    heading("Integridad (SHA-256)")
    st.caption(f"{data_dir} (solo lectura). Ejecución {res.run_id}, reglas {cfg.rules_version}.")
    st.dataframe(pd.DataFrame([{"Archivo": f, "Estado": v["status"], "SHA-256 registrado": v["registered"]}
                               for f, v in _ver.items()]), width="stretch", hide_index=True)
    if n_hash_ok != len(_ver):
        st.error("Archivos modificados. Vuelve a ejecutar.")

    panel_seguridad.render(res, data_dir, st.session_state.ver, n_hash_ok, len(_ver))

    for cid, p in cfg.profiles.items():
        with st.expander(f"Perfil {cid} v{p.profile_version}"):
            c1, c2 = st.columns(2)
            c1.markdown("**Columnas**")
            c1.dataframe(pd.DataFrame([{"Campo NEXUS": k, "Encabezado en la fuente": v} for k, v in p.columns.items()]),
                         width="stretch", hide_index=True)
            c2.markdown("**Cuentas**")
            c2.dataframe(pd.DataFrame([{"Cuenta local": k, "Codigo": v} for k, v in p.accounts.items()]),
                         width="stretch", hide_index=True)
            st.caption(f"Signo: {p.sign_convention} | moneda: {p.currency_mode}"
                       f"{' (' + p.currency_key + ')' if p.currency_key else ''} | hojas: "
                       f"{', '.join(p.sheets) or '-'} | hash {p.profile_hash[:12]}...")

# ------------------------------------------------------------------ Asistente (prototipo, opcional)
if section == "Asistente":
    from asistente import tab as tab_asistente
    tab_asistente.render(res, period, escenario, demo, props_abiertas)
