"""NEXUS - pantalla para ver el avance del motor (Streamlit).

La interfaz NO calcula nada: solo muestra lo que devuelve el motor (nexus.pipeline.run).
Ejecutar:  .venv/bin/streamlit run app.py
"""
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
import streamlit as st

from nexus.audit import verify_hashes
from nexus.consolidation import trace
from nexus.pipeline import run
from nexus.ui import extras

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title="NEXUS - Consolidacion", layout="wide")


def m(d, plus=False):
    if d is None:
        return "n/c"
    s = f"{d.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):,.2f}"
    return ("+" + s) if plus and d > 0 else s


@st.cache_resource(show_spinner="Ejecutando el motor...")
def load(data_dir: str, profiles_dir: str, version: int):
    return run(data_dir, profiles_dir=profiles_dir or None)


# ------------------------------------------------------------------ barra lateral
with st.sidebar:
    st.title("NEXUS")
    st.caption("Motor de consolidacion financiera multiempresa. Datos SINTETICOS (Grupo Ferrex).")
    data_dir = st.text_input("Carpeta del servidor con los archivos (solo lectura)", str(ROOT / "data" / "synthetic"))
    profiles_dir = st.text_input("Carpeta de perfiles (vacio = deteccion automatica)", str(ROOT / "profiles"))
    if "ver" not in st.session_state:
        st.session_state.ver = 0
    if st.button("Volver a ejecutar el motor"):
        st.session_state.ver += 1
    try:
        res = load(data_dir, profiles_dir, st.session_state.ver)
    except Exception as e:  # noqa: BLE001 - se muestra el error tal cual
        st.error(f"No se pudo ejecutar el motor: {e}")
        st.stop()
    period = st.radio("Periodo", list(res.periods), format_func=lambda p: f"{p} ({res.periods[p].kind})")
    st.caption(f"Ejecucion {res.run_id} | reglas {res.config.rules_version}")
    st.success("Fuente: carpeta del servidor")
    st.caption("NEXUS lee los archivos en solo lectura, sin subida manual y sin conexion a internet.")

pr = res.periods[period]
cfg = res.config

# ------------------------------------------------------------------ encabezado del periodo
head, badge = st.columns([4, 1])
head.header(f"Consolidado {period} en USD")
if pr.provisional:
    badge.error("PROVISIONAL")
else:
    badge.success("DEFINITIVO")
if pr.provisional:
    with st.container(border=True):
        st.markdown("**Por que es provisional**")
        for why in pr.provisional_reasons:
            st.markdown(f"- {why}")
        if pr.utility_range:
            lo, hi = pr.utility_range
            c1, c2 = st.columns(2)
            c1.metric("Utilidad neta mostrada", m(pr.summary["utilidad_neta"]))
            c2.metric("Registros fuera del consolidado", len(pr.excluded))
            st.markdown(f"**Rango posible de utilidad neta si se resolviera lo pendiente:** {m(lo)} a {m(hi)} USD")
            st.caption("El rango es informativo: ninguna cifra del consolidado se modifica y los impuestos no se "
                       "recalculan.")
else:
    st.metric("Utilidad neta", m(pr.summary["utilidad_neta"]))
extras.render_header(res, period, data_dir, profiles_dir)

tab_res, tab_alert, tab_hall, tab_trace, tab_prof, tab_ind, tab_var, tab_sim, tab_help = st.tabs(
    ["Resultados y balance", "Alertas y exclusiones", "Hallazgos", "Trazabilidad", "Perfiles por empresa",
     "Indicadores", "Variaciones", "Simulador", "Ayuda"])
_dirs = [d for d in (data_dir, profiles_dir) if d]
_ver = verify_hashes(res.input_hashes, _dirs)

# ------------------------------------------------------------------ a/b) estados financieros
with tab_res:
    s, n = pr.summary, pr.naive_summary
    st.subheader("Estado de resultados")
    rows = [("Ingresos", "ingresos"), ("(-) Costo de ventas", "costo_ventas"),
            ("(-) Gastos operativos", "gastos_operativos"), ("= EBIT", "ebit"),
            ("(-) Gastos financieros", "gastos_financieros"), ("(-) Impuestos", "impuestos"),
            ("= Utilidad neta", "utilidad_neta")]
    st.dataframe(pd.DataFrame([{"Concepto": lbl, "Suma ingenua": m(n[k]), "Eliminaciones": m(s[k] - n[k], True),
                                "Consolidado": m(s[k])} for lbl, k in rows]),
                 width="stretch", hide_index=True)
    st.caption("Suma ingenua = sumar las empresas sin eliminar operaciones entre ellas. La utilidad no cambia al "
               "eliminar: lo que sale de ingresos tambien sale de costos.")
    st.subheader("Balance general")
    brow = [("Activo total", "activo_total"), ("Pasivo total", "pasivo_total"), ("Patrimonio", "patrimonio")]
    df = pd.DataFrame([{"Concepto": lbl, "Suma ingenua": m(n[k]), "Eliminaciones": m(s[k] - n[k], True),
                        "Consolidado": m(s[k])} for lbl, k in brow])
    st.dataframe(df, width="stretch", hide_index=True)
    diff = s["activo_menos_pasivo_y_patrimonio"]
    (st.success if m(diff) == "0.00" else st.error)(f"Activo - (Pasivo + Patrimonio) = {m(diff)} USD")
    with st.expander("Detalle por cuenta del catalogo comun"):
        st.dataframe(pd.DataFrame([{"Cuenta": c, "Nombre": cfg.catalog[c].name, "Antes de eliminar": m(ln.gross_usd),
                                    "Consolidado": m(ln.amount_usd)} for c, ln in pr.lines.items()]),
                     width="stretch", hide_index=True)

# ------------------------------------------------------------------ c) alertas, exclusiones, discrepancias
with tab_alert:
    st.subheader("Alertas")
    fs = [f for f in res.findings if f.period in (None, period)]
    if fs:
        st.dataframe(pd.DataFrame([{"Severidad": f.severity, "Regla": f.rule_id, "Empresa": f.company_id,
                                    "Que paso": f.message, "Impacto estimado": f.impact or ""} for f in fs]),
                     width="stretch", hide_index=True)
    else:
        st.info("Sin alertas en este periodo.")

    st.subheader("Registros fuera del consolidado (nada se excluye en silencio)")
    if pr.excluded:
        st.dataframe(pd.DataFrame([{"Empresa": e.company_id, "Estado": e.status, "Registro": e.record_id,
                                    "Importe original": m(e.amount_original), "Moneda": e.currency or "",
                                    "Importe USD": m(e.amount_usd), "Motivo": "; ".join(e.reasons)}
                                   for e in pr.excluded]), width="stretch", hide_index=True)
        tot = ", ".join(f"{k}: {m(v)} USD" for k, v in pr.excluded_usd_by_status.items())
        st.caption(f"Total fuera, por estado: {tot or 'sin importes convertibles'}."
                   + (f" {pr.excluded_not_convertible} registro(s) sin conversion posible (n/c)."
                      if pr.excluded_not_convertible else ""))
    else:
        st.info("Todo lo cargado entro al consolidado.")

    st.subheader("Impacto en utilidad neta de lo que quedo fuera")
    if pr.impact_ranges:
        st.dataframe(pd.DataFrame([{"Registro": i.record_id, "Excluido": m(i.utility_excluded),
                                    "Como viene": m(i.utility_as_is, True), "Corregido": m(i.utility_corrected, True),
                                    "Nota": i.note} for i in pr.impact_ranges]),
                     width="stretch", hide_index=True)
    else:
        st.caption("Ningun registro bloqueado o pendiente afecta la utilidad en este periodo.")

    st.subheader("Intercompania")
    ms = [x for x in res.matches if x.period == period]
    ok = [x for x in ms if x.status == "RECONCILED"]
    bad = [x for x in ms if x.status != "RECONCILED"]
    st.caption(f"{len(ok)} operaciones conciliadas y eliminadas, {len(bad)} abiertas (no se eliminan).")
    if bad:
        _g = {}
        for x in bad:
            _g.setdefault((x.seller_id, x.buyer_id, x.reference), []).append(x)
        st.dataframe(pd.DataFrame([{"Estado": v[0].status, "Vendedor": k[0], "Comprador": k[1], "Referencia": k[2],
                                    "Afecta": " y ".join("operacion (venta)" if y.statement == "ER" else "saldo (CxC y CxP)"
                                                         for y in sorted(v, key=lambda y: y.statement != "ER")),
                                    "USD vendedor": m(v[0].seller_usd), "USD comprador": m(v[0].buyer_usd),
                                    "Diferencia": m(v[0].difference_usd)} for k, v in _g.items()]),
                     width="stretch", hide_index=True)
        st.caption("Cada discrepancia se muestra una sola vez: la misma diferencia afecta la operacion (la venta) y el "
                   "saldo (cuenta por cobrar y por pagar). No se elimina ninguna de las dos.")
    with st.expander("Ver las eliminaciones conciliadas"):
        st.dataframe(pd.DataFrame([{"Vendedor": x.seller_id, "Comprador": x.buyer_id, "Referencia": x.reference,
                                    "Tipo": "Operacion" if x.statement == "ER" else "Saldo",
                                    "USD vendedor": m(x.seller_usd), "USD comprador": m(x.buyer_usd)} for x in ok]),
                     width="stretch", hide_index=True)

# ------------------------------------------------------------------ d) trazabilidad
with tab_trace:
    st.subheader("De una cifra a su registro original")
    groups = {"Ingresos": "ingreso", "Costo de ventas": "costo", "Gastos operativos": "gasto_operativo",
              "Gastos financieros": "gasto_financiero", "Impuestos": "impuesto", "Activo": "activo",
              "Pasivo": "pasivo", "Patrimonio": "patrimonio"}
    options = {f"{lbl} (total)": [c for c, a in cfg.catalog.items() if a.cls == cls] for lbl, cls in groups.items()}
    options.update({f"{c} - {cfg.catalog[c].name}": [c] for c in pr.lines})
    choice = st.selectbox("Cifra", list(options))
    traces = [trace(period, c, res) for c in options[choice]]
    gross = sum((t["gross_usd"] for t in traces), Decimal(0))
    final = sum((t["amount_usd"] for t in traces), Decimal(0))
    c1, c2, c3 = st.columns(3)
    c1.metric("Suma de registros", m(gross))
    c2.metric("Ajustes (eliminaciones)", m(final - gross, True))
    c3.metric("Cifra en el consolidado", m(final))
    recs = [{"Cuenta": t["account_code"], "Empresa": x["company_id"], "Archivo": x["file"],
             "Hoja": x["sheet"] or "-", "Fila": x["row"], "Cuenta local": x["account_local"],
             "Importe original": m(x["amount_original"]), "Moneda": x["currency"],
             "Tasa": str(x["fx_rate"]), "Orientacion": "multiplica (USD por unidad local)"
             if x["fx_orientation"] == "USD_PER_LOCAL" else "divide (local por USD)",
             "Importe USD": m(x["amount_usd"]), "Contraparte": x["counterparty_id"] or "",
             "ID transaccion": x["transaction_id"] or ""} for t in traces for x in t["records"]]
    st.markdown(f"**Registros fuente ({len(recs)})**")
    st.dataframe(pd.DataFrame(recs), width="stretch", hide_index=True)
    adjs = [{"Ajuste": a["adjustment_id"], "Tipo": a["kind"], "USD": m(a["amount_usd"], True), "Regla": a["rule"],
             "Motivo": a["reason"]} for t in traces for a in t["adjustments"]]
    st.markdown(f"**Ajustes aplicados ({len(adjs)})**")
    if adjs:
        st.dataframe(pd.DataFrame(adjs), width="stretch", hide_index=True)
    else:
        st.caption("Esta cifra no tiene ajustes.")

# ------------------------------------------------------------------ e) perfiles
with tab_prof:
    st.subheader("Perfiles de integracion por empresa")
    icon = {"MATCHED": "Coincide con el perfil", "REVIEW": "EN REVISION (no coincide)", "AUTO": "Sin perfil (auto)"}
    rows = []
    for cid, c in cfg.companies.items():
        rep, p = res.load_reports.get(cid), cfg.profiles.get(cid)
        rows.append({"Empresa": cid, "Nombre": c.name, "Moneda": c.currency,
                     "Formato": p.source.type.upper() if p else "-", "Archivo": c.file,
                     "Version": p.profile_version if p else "-",
                     "Aprobado por": (p.approved_by or "PENDIENTE") if p else "-",
                     "Ultima carga": icon.get(rep.status, rep.status) if rep else "-",
                     "Registros": rep.n_records if rep else 0})
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    revs = [r for r in res.load_reports.values() if r.status == "REVIEW"]
    for r in revs:
        st.error(f"{r.company_id} ({r.file}) quedo en REVISION y no aporta registros:\n\n- " + "\n- ".join(r.reasons))
    for r in res.load_reports.values():
        for note in r.notes:
            st.warning(f"{r.company_id}: {note}")
    st.subheader("Integridad de los archivos leidos (SHA-256)")
    st.caption(f"Fuente: carpeta del servidor, solo lectura: {data_dir}. El hash se registro al leer y se vuelve a "
               f"calcular ahora.")
    st.dataframe(pd.DataFrame([{"Archivo": f, "Estado": v["status"], "SHA-256 registrado": v["registered"]}
                               for f, v in _ver.items()]), width="stretch", hide_index=True)
    if any(v["status"] != "OK" for v in _ver.values()):
        st.error("Algun archivo cambio o falta desde que se leyo. Vuelve a ejecutar el motor.")
    if not cfg.profiles:
        st.info("No hay perfiles cargados: el motor uso deteccion automatica de formatos.")
    pend = [c for c, p in cfg.profiles.items() if p.approval_status != "APPROVED"]
    if pend:
        st.warning("Perfiles pendientes de aprobacion: " + ", ".join(pend) +
                   ". Se usan, pero nadie ha firmado la equivalencia de cuentas.")
    for cid, p in cfg.profiles.items():
        with st.expander(f"Detalle del perfil {cid} (v{p.profile_version})"):
            a, b = st.columns(2)
            a.markdown("**Columnas esperadas en la fuente**")
            a.dataframe(pd.DataFrame([{"Campo NEXUS": k, "Encabezado en la fuente": v} for k, v in p.columns.items()]),
                        width="stretch", hide_index=True)
            b.markdown("**Equivalencias de cuentas**")
            b.dataframe(pd.DataFrame([{"Cuenta local": k, "Codigo": v} for k, v in p.accounts.items()]),
                        width="stretch", hide_index=True)
            st.caption(f"Signo: {p.sign_convention} | moneda: {p.currency_mode}"
                       f"{' (' + p.currency_key + ')' if p.currency_key else ''} | hojas: "
                       f"{', '.join(p.sheets) or '-'} | hash {p.profile_hash[:12]}...")
extras.render_extra_tabs(res, period, data_dir, profiles_dir, tab_ind, tab_var, tab_sim, tab_help, tab_hall)
