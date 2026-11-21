"""NEXUS - interfaz Streamlit.

La interfaz NO calcula cifras del consolidado: solo ordena y muestra lo que devuelve el motor
(nexus.pipeline.run). Las secciones se eligen en el menu desplegable de la barra lateral (key "nav");
Hallazgos, Indicadores, Variaciones, Simulador y Ayuda viven en nexus/ui/ y las mantiene su autor.

Ejecutar:  streamlit run app.py
"""
import sys
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import altair as alt  # ya viene con streamlit (no es una dependencia nueva)
import pandas as pd
import streamlit as st

from nexus.audit import verify_hashes
from nexus.consolidation import trace
from nexus.pipeline import run
from nexus.schemas import BLOCK, BLOCKED, EXCLUDED_DUPLICATE, INFO, PENDING_MAPPING, WARN
from nexus.ui import extras, tab_ayuda, tab_hallazgos, tab_indicadores, tab_simulador, tab_variaciones
from nexus.variance import view

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title="NEXUS | Consolidación", layout="wide", initial_sidebar_state="expanded")

# ------------------------------------------------------------------ estilo (sin fuentes externas: corre sin red)
# Linea grafica del pitch: carbon, naranja NEXUS y blanco hueso. Los colores de estado (lista / revisar /
# bloqueada) se eligieron para no confundirse con el naranja de marca, tambien con daltonismo.
st.markdown("""<style>
:root{--bg:#181716;--panel:#23211F;--line:#3B3835;--ink:#F3F1ED;--muted:#A8A29B;--brand:#F05A28;
--red:#FF5C93;--amber:#F7C948;--green:#3DD68C;
--display:"Inter Display","Inter Tight","Segoe UI Black","Arial Black","Helvetica Neue",Arial,sans-serif;}
.block-container{padding-top:1.6rem;max-width:1380px}
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
.nx-fig-v.red{color:var(--red)} .nx-fig-v.amber{color:var(--amber)}
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
.nx-state{font-size:.82rem;font-weight:700}
.nx-state.green{color:var(--green)}.nx-state.amber{color:var(--amber)}.nx-state.red{color:var(--red)}
.nx-ok{color:var(--green);font-size:.85rem}
.st-key-nx_badge [data-testid="stAlertContainer"]{padding:.45rem .8rem}
.st-key-nx_badge p{white-space:nowrap;font-weight:600;letter-spacing:.03em;font-size:.88rem}
section[data-testid="stSidebar"] [data-testid="stAlertContainer"]{padding:.5rem .75rem}
.stTabs [data-baseweb="tab-list"]{gap:4px;border-bottom:1px solid var(--line)}
</style>""", unsafe_allow_html=True)

MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
          "noviembre", "diciembre"]
KIND = {"real": "cifras reales", "presupuesto": "presupuesto"}
SECTIONS = ["Resumen", "Estados financieros", "Alertas y errores", "Hallazgos", "Intercompañía",
            "Trazabilidad", "Indicadores", "Variaciones", "Simulador", "Perfiles e integridad", "Ayuda"]
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


# ------------------------------------------------------------------ barra lateral
with st.sidebar:
    html('<div class="nx-word">NEXUS</div><div class="nx-word-sub">Muchas empresas.<br>Un solo número.</div>')
    section = st.selectbox("Sección", SECTIONS, key="nav")
    period_box = st.container()
    status_box = st.container()
    with st.expander("Configuración de la fuente"):
        data_dir = st.text_input("Carpeta del servidor con los archivos (solo lectura)", str(ROOT / "data" / "synthetic"))
        profiles_dir = st.text_input("Carpeta de perfiles (vacío = detección automática)", str(ROOT / "profiles"))
        if "ver" not in st.session_state:
            st.session_state.ver = 0
        if st.button("Volver a ejecutar el motor"):
            st.session_state.ver += 1

try:
    res = load(data_dir, profiles_dir, st.session_state.ver)
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
        html(f'<div class="nx-ok">Archivos sin cambios: {n_hash_ok} de {len(_ver)} (SHA-256)</div>')
    else:
        st.error(f"{pl(len(_ver) - n_hash_ok, 'archivo cambió', 'archivos cambiaron')} o falta desde que se leyó. "
                 f"Vuelve a ejecutar el motor.")
    st.caption(("Datos de prueba (sintéticos). " if synthetic else "") +
               f"Ejecución {res.run_id}, reglas {cfg.rules_version}. Sin subida manual y sin internet.")
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
ic_groups = {}
for x in ic_open:
    ic_groups.setdefault((x.seller_id, x.buyer_id, x.reference), []).append(x)
unresolved = [e for e in pr.excluded if e.status in (BLOCKED, PENDING_MAPPING)]
dups = [e for e in pr.excluded if e.status == EXCLUDED_DUPLICATE]
findings = sorted([f for f in res.findings if f.period in (None, period)],
                  key=lambda f: (SEV_ORDER.get(f.severity, 9), f.company_id or "", f.rule_id))
currencies = sorted({c.currency for c in cfg.companies.values()})
cur_txt = ", ".join(currencies[:-1]) + f" y {currencies[-1]}" if len(currencies) > 1 else "".join(currencies)

# ------------------------------------------------------------------ encabezado
head, badge_col = st.columns([5, 1.1], vertical_alignment="center")
with head:
    html(f'<div class="nx-title">Consolidado de {escape(month(period))}</div>'
         f'<div class="nx-lede">{escape(KIND.get(pr.kind, pr.kind).capitalize())}. '
         f'{len(cfg.companies)} empresas en {escape(cur_txt)}, todo convertido a dólares con la tasa del mes.</div>')
with badge_col.container(key="nx_badge"):
    if pr.provisional:
        st.error("PROVISIONAL", icon=":material/schedule:")
    else:
        st.success("COMPLETO", icon=":material/check_circle:")

elim_ing = s["ingresos"] - n["ingresos"]
figures([
    ("Ingresos consolidados (USD)", m(s["ingresos"]),
     f"Las empresas reportaron {m(n['ingresos'])}; se quitaron {m(-elim_ing)} de ventas entre ellas.", ""),
    ("Utilidad neta (USD)", m(s["utilidad_neta"]),
     f"Puede quedar entre {m(pr.utility_range[0])} y {m(pr.utility_range[1])} al resolver lo pendiente."
     if pr.utility_range else "Nada pendiente la cambia.", ""),
    ("Registros bloqueados", len(unresolved),
     ("No entran al consolidado hasta corregirse." if unresolved else "Todo lo cargado es válido.")
     + (f" Aparte, {pl(len(dups), 'duplicado se excluyó', 'duplicados se excluyeron')} con ajuste." if dups else ""),
     "red" if unresolved else ""),
    ("Diferencias entre empresas", len(ic_groups),
     f"{pl(len(ic_groups), 'operación no cuadra', 'operaciones no cuadran')} y no se eliminan; "
     f"{len(ic_ok)} sí cuadran." if ic_open else f"Las {len(ic_ok)} operaciones entre empresas cuadran.",
     "amber" if ic_open else ""),
])

html(f'<div class="nx-section">{escape(section)}</div>')

# ------------------------------------------------------------------ Resumen
if section == "Resumen":
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
        parts = [("Queda en el consolidado", lambda cid: gross[cid] + elim[cid]),
                 ("Venta a otra empresa del grupo (se elimina)", lambda cid: -elim[cid])]
        chart = pd.DataFrame([{"Empresa": cfg.companies[cid].name, "ID": cid, "Parte": lbl, "orden": i,
                               "USD": float(fn(cid)), "Importe": f"{m(fn(cid))} USD",
                               "Reportado": f"{m(gross[cid])} USD"}
                              for cid in cfg.companies for i, (lbl, fn) in enumerate(parts)])
        if gross:
            # 2 px del color de fondo entre segmentos y extremos redondeados (guia de graficos del equipo)
            bars = alt.Chart(chart).mark_bar(stroke="#181716", strokeWidth=2, cornerRadiusEnd=4).encode(
                y=alt.Y("Empresa:N", title=None, sort=None, axis=alt.Axis(labelLimit=220, labelFontSize=12)),
                x=alt.X("USD:Q", title=None, stack="zero", axis=alt.Axis(format=",.0f", grid=True, tickCount=5)),
                color=alt.Color("Parte:N", title=None, legend=alt.Legend(orient="bottom", direction="horizontal",
                                                                         labelLimit=400, columns=1),
                                scale=alt.Scale(domain=[p[0] for p in parts], range=["#D9D3CB", "#F05A28"])),
                order=alt.Order("orden:Q"),
                tooltip=[alt.Tooltip("Empresa:N"), alt.Tooltip("ID:N"), alt.Tooltip("Parte:N"),
                         alt.Tooltip("Importe:N"), alt.Tooltip("Reportado:N", title="Reportado por la empresa")],
            ).properties(height=44 * len(cfg.companies) + 40)
            st.altair_chart(bars, use_container_width=True)
            ok_tot = (sum(gross.values(), Decimal(0)) == n["ingresos"]
                      and sum(gross.values(), Decimal(0)) + sum(elim.values(), Decimal(0)) == s["ingresos"])
            st.caption("Cada barra es lo que reportó la empresa. La parte naranja es lo que le vendió a otra empresa "
                       "del grupo: se resta para no contar la misma venta dos veces. "
                       + ("Los totales cuadran con el estado de resultados." if ok_tot else
                          "Ojo: este desglose no cuadra con el estado de resultados."))
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
                red.append("el archivo no coincide con su perfil")
            if cid in pr.missing_companies:
                red.append("no mandó datos de este período")
            if n_out:
                red.append(pl(n_out, "registro bloqueado", "registros bloqueados"))
            if n_block and not n_out:
                red.append(pl(n_block, "alerta que bloquea", "alertas que bloquean"))
            if n_ic:
                amber.append(pl(n_ic, "venta entre empresas no cuadra", "ventas entre empresas no cuadran"))
            if n_warn:
                amber.append(pl(n_warn, "advertencia", "advertencias"))
            if n_dup:
                amber.append(pl(n_dup, "duplicado excluido", "duplicados excluidos"))
            if prof is not None and prof.approval_status != "APPROVED":
                amber.append("perfil sin aprobar")
            tone = "red" if red else ("amber" if amber else "green")
            why = ", ".join(red + amber) or "sin observaciones"
            label = {"red": "Bloqueada", "amber": "Revisar", "green": "Lista"}[tone]
            rows.append(f'<div class="nx-row"><span class="nx-dot {tone}"></span><div>'
                        f'<div class="nx-row-t">{escape(c.name)}</div>'
                        f'<div class="nx-row-s">{escape(cid)} en {escape(c.currency)}: {escape(why)}</div></div>'
                        f'<span class="nx-state {tone}">{label}</span></div>')
        html('<div class="nx-list">' + "".join(rows) + "</div>")

    st.write("")
    a, b = st.columns(2, gap="large")
    with a:
        heading("Qué falta para cerrar el período")
        if pr.provisional:
            with st.container(border=True):
                for why in pr.provisional_reasons:
                    st.markdown(f"- {why}")
                if pr.utility_range:
                    lo, hi = pr.utility_range
                    st.markdown(f"**Rango posible de utilidad neta si se resolviera lo pendiente:** {m(lo)} a "
                                f"{m(hi)} USD")
                st.caption("El rango es solo informativo: no cambia ninguna cifra y no recalcula impuestos.")
        else:
            st.success("Período completo: todo lo cargado entró al consolidado y no hay alertas pendientes.")
    with b:
        heading("Para atender primero")
        top = [f for f in findings if f.severity in (BLOCK, WARN)][:4]
        if top:
            with st.container(border=True):
                for f in top:
                    tip = f" Sugerencia: {f.suggestion}." if f.suggestion else ""
                    st.markdown(f"**{f.company_id or 'Grupo'}** ({SEV_LABEL.get(f.severity, f.severity).lower()}): "
                                f"{f.message}{tip}")
        else:
            st.caption("No hay nada urgente en este período.")
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
        st.caption("Suma de empresas: lo que reportó cada una, sumado tal cual. La utilidad no cambia al eliminar, "
                   "porque lo que sale de ingresos también sale de costos.")
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
    st.markdown(f"En este período hay **{pl(by_sev[BLOCK], 'alerta que bloquea', 'alertas que bloquean')} el "
                f"cierre**, {pl(by_sev[WARN], 'advertencia', 'advertencias')} para revisar y "
                f"{pl(by_sev[INFO], 'nota', 'notas')}.")
    if findings:
        st.dataframe(pd.DataFrame([{"Tipo": SEV_LABEL.get(f.severity, f.severity), "Empresa": f.company_id or "Grupo",
                                    "Qué pasó": f.message, "Qué hacer": f.suggestion,
                                    "Impacto estimado": f.impact or "", "Regla": f.rule_id}
                                   for f in findings]),
                     width="stretch", hide_index=True)
    else:
        st.info("Sin alertas en este período.")

    heading("Registros que quedaron fuera del consolidado")
    if pr.excluded:
        st.dataframe(pd.DataFrame([{"Empresa": e.company_id, "Estado": STATUS_LABEL.get(e.status, e.status),
                                    "Motivo": "; ".join(e.reasons), "Importe original": m(e.amount_original),
                                    "Moneda": e.currency or "", "Importe USD": m(e.amount_usd),
                                    "Registro": e.record_id, "Código": e.status} for e in pr.excluded]),
                     width="stretch", hide_index=True)
        tot = ", ".join(f"{STATUS_LABEL.get(k, k).lower()} {m(v)} USD" for k, v in pr.excluded_usd_by_status.items())
        st.caption(f"Nada se excluye en silencio. Total fuera: {tot or 'sin importes convertibles'}."
                   + (f" {pl(pr.excluded_not_convertible, 'registro no se pudo', 'registros no se pudieron')} "
                      f"convertir (n/c)." if pr.excluded_not_convertible else ""))
    else:
        st.info("Todo lo cargado entró al consolidado.")

    heading("Cuánto movería la utilidad lo que quedó fuera")
    if pr.impact_ranges:
        st.dataframe(pd.DataFrame([{"Registro": i.record_id, "Empresa": i.company_id, "Excluido": m(i.utility_excluded),
                                    "Si entra como viene": m(i.utility_as_is, True),
                                    "Si se corrige": m(i.utility_corrected, True), "Nota": i.note}
                                   for i in pr.impact_ranges]),
                     width="stretch", hide_index=True)
    else:
        st.caption("Ningún registro bloqueado o pendiente afecta la utilidad en este período.")

# ------------------------------------------------------------------ Intercompañía
if section == "Intercompañía":
    figures([
        ("Operaciones que cuadran", len(ic_ok), "Se eliminan para no contar dos veces la misma venta.", ""),
        ("Operaciones que no cuadran", len(ic_groups), "Quedan abiertas: no se elimina nada hasta conciliar.",
         "amber" if ic_open else ""),
        ("Tolerancia (USD)", m(cfg.ic_tolerance_usd), "Diferencia máxima para dar una operación por conciliada.", ""),
    ])
    heading("Operaciones que no cuadran")
    if ic_open:
        st.dataframe(pd.DataFrame([{"Vendedor": k[0], "Comprador": k[1], "Referencia": k[2],
                                    "Afecta": " y ".join("operacion (venta)" if y.statement == "ER"
                                                         else "saldo (CxC y CxP)"
                                                         for y in sorted(v, key=lambda y: y.statement != "ER")),
                                    "USD vendedor": m(v[0].seller_usd), "USD comprador": m(v[0].buyer_usd),
                                    "Diferencia": m(v[0].difference_usd), "Estado": v[0].status}
                                   for k, v in ic_groups.items()]),
                     width="stretch", hide_index=True)
        st.caption("Cada discrepancia se muestra una sola vez: la misma diferencia afecta la operación (la "
                   "venta) y el saldo (cuenta por cobrar y por pagar). No se elimina ninguna de las dos.")
    else:
        st.success("Todas las operaciones entre empresas de este período cuadran.")
    with st.expander(f"Ver las {len(ic_ok)} operaciones eliminadas"):
        st.dataframe(pd.DataFrame([{"Vendedor": x.seller_id, "Comprador": x.buyer_id, "Referencia": x.reference,
                                    "Tipo": "Operación" if x.statement == "ER" else "Saldo",
                                    "USD vendedor": m(x.seller_usd), "USD comprador": m(x.buyer_usd)} for x in ic_ok]),
                     width="stretch", hide_index=True)

# ------------------------------------------------------------------ Trazabilidad
if section == "Trazabilidad":
    st.markdown("Elige una cifra del consolidado y mira de qué filas de qué archivos sale.")
    groups = {"Ingresos": "ingreso", "Costo de ventas": "costo", "Gastos operativos": "gasto_operativo",
              "Gastos financieros": "gasto_financiero", "Impuestos": "impuesto", "Activo": "activo",
              "Pasivo": "pasivo", "Patrimonio": "patrimonio"}
    options = {f"{lbl} (total)": [c for c, a in cfg.catalog.items() if a.cls == cls] for lbl, cls in groups.items()}
    options.update({f"{c} - {cfg.catalog[c].name}": [c] for c in pr.lines})
    choice = st.selectbox("Cifra", list(options), key="traza_cifra")
    traces = [trace(period, c, res) for c in options[choice]]
    tr_gross = sum((t["gross_usd"] for t in traces), Decimal(0))
    tr_final = sum((t["amount_usd"] for t in traces), Decimal(0))
    figures([
        ("Suma de los registros (USD)", m(tr_gross), "Lo que reportaron las empresas.", ""),
        ("Eliminaciones (USD)", m(tr_final - tr_gross, True), "Ventas entre empresas que cuadraron.", ""),
        ("Cifra en el consolidado (USD)", m(tr_final), "Lo que aparece en los estados financieros.", ""),
    ])
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
    heading(f"Ajustes aplicados ({len(adjs)})")
    if adjs:
        st.dataframe(pd.DataFrame(adjs), width="stretch", hide_index=True)
    else:
        st.caption("Esta cifra no tiene ajustes.")

# ------------------------------------------------------------------ secciones de otros integrantes
if section == "Hallazgos":
    tab_hallazgos.render(res, period)
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
    heading("Cómo se lee el archivo de cada empresa")
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
        st.info("No hay perfiles cargados: el motor detectó los formatos automáticamente.")
    pend = [c for c, p in cfg.profiles.items() if p.approval_status != "APPROVED"]
    if pend:
        st.warning("Perfiles pendientes de aprobación: " + ", ".join(pend) +
                   ". Se usan, pero nadie ha firmado la equivalencia de cuentas.")

    heading("Integridad de los archivos leídos (SHA-256)")
    st.caption(f"Carpeta del servidor, solo lectura: {data_dir}. La huella se tomó al leer cada archivo y se vuelve a "
               f"calcular ahora; si alguien lo cambió, aparece aquí.")
    st.dataframe(pd.DataFrame([{"Archivo": f, "Estado": v["status"], "SHA-256 registrado": v["registered"]}
                               for f, v in _ver.items()]), width="stretch", hide_index=True)
    if n_hash_ok != len(_ver):
        st.error("Algún archivo cambió o falta desde que se leyó. Vuelve a ejecutar el motor.")

    for cid, p in cfg.profiles.items():
        with st.expander(f"Perfil de {cid} (versión {p.profile_version})"):
            c1, c2 = st.columns(2)
            c1.markdown("**Columnas que espera en el archivo**")
            c1.dataframe(pd.DataFrame([{"Campo NEXUS": k, "Encabezado en la fuente": v} for k, v in p.columns.items()]),
                         width="stretch", hide_index=True)
            c2.markdown("**Equivalencia de cuentas**")
            c2.dataframe(pd.DataFrame([{"Cuenta local": k, "Codigo": v} for k, v in p.accounts.items()]),
                         width="stretch", hide_index=True)
            st.caption(f"Signo: {p.sign_convention} | moneda: {p.currency_mode}"
                       f"{' (' + p.currency_key + ')' if p.currency_key else ''} | hojas: "
                       f"{', '.join(p.sheets) or '-'} | hash {p.profile_hash[:12]}...")
