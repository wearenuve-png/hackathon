"""Panel 'Resumen de la carga' en lenguaje simple: que se leyo, que esta bien, que se corrigio solo, que espera tu
decision y que esta bloqueado, con el estado de cada archivo (verde / amarillo / rojo) y su huella digital."""
from collections import defaultdict
from html import escape
from typing import Dict, List

import streamlit as st

from ..schemas import BLOCKED, EXCLUDED_DUPLICATE, OK, PENDING_MAPPING, TOTAL


def calcular(res, props=None) -> Dict:
    """props: propuestas abiertas (nexus.ui.correcciones.proponer). Puro: no usa Streamlit."""
    props = props or []
    cfg = res.config
    por = defaultdict(lambda: defaultdict(int))
    for r in res.records:
        c = por[r.company_id]
        c["registros"] += 1
        c["correctos"] += r.status in (OK, TOTAL)
        c["auto"] += r.status == EXCLUDED_DUPLICATE
        c["bloqueados"] += r.status == BLOCKED
        c["pendientes"] += r.status == PENDING_MAPPING
    abiertas = [p for p in props if p.aprobable]
    for p in abiertas:
        por[p.company_id or "GRUPO"]["propuestas"] += 1
    faltan = {cid for pr in res.periods.values() for cid in pr.missing_companies}
    avisos = defaultdict(int)
    for f in res.findings:
        if f.severity == "WARN" and f.company_id:
            avisos[f.company_id] += 1
    archivos: List[dict] = []
    for cid, comp in cfg.companies.items():
        rep, c = res.load_reports.get(cid), por[cid]
        rojo = (rep is not None and rep.status == "REVIEW") or c["bloqueados"] > 0 or cid in faltan
        amar = c["pendientes"] > 0 or c["propuestas"] > 0 or c["auto"] > 0 or avisos[cid] > 0
        estado = "rojo" if rojo else "amarillo" if amar else "verde"
        motivos = []
        if rep is not None and rep.status == "REVIEW":
            motivos.append("el archivo no coincide con su perfil: no se leyó")
        if c["bloqueados"]:
            motivos.append(f"{c['bloqueados']} registro(s) bloqueado(s)")
        if cid in faltan:
            motivos.append("falta algún mes")
        if c["pendientes"]:
            motivos.append(f"{c['pendientes']} cuenta(s) sin confirmar")
        if c["propuestas"]:
            motivos.append(f"{c['propuestas']} corrección(es) esperan tu decisión")
        if c["auto"]:
            motivos.append(f"{c['auto']} duplicado(s) corregido(s) solo")
        archivos.append({"empresa": cid, "nombre": comp.name, "archivo": comp.file, "estado": estado,
                         "registros": c["registros"], "correctos": c["correctos"], "auto": c["auto"],
                         "bloqueados": c["bloqueados"], "pendientes": c["pendientes"],
                         "motivo": "; ".join(motivos) or "sin observaciones",
                         "huella": res.input_hashes.get(comp.file, "")})
    leidos = sum(1 for r in res.load_reports.values() if r.status != "REVIEW")
    tot = {k: sum(c[k] for c in por.values()) for k in ("registros", "correctos", "auto", "bloqueados", "pendientes")}
    return {"archivos": archivos, "archivos_leidos": leidos, "archivos_total": len(cfg.companies),
            "registros": tot["registros"], "correctos": tot["correctos"], "auto": tot["auto"],
            "bloqueados": tot["bloqueados"], "propuestas_abiertas": len(abiertas),
            "pendientes": len(abiertas) + tot["pendientes"], "sin_confirmar": tot["pendientes"]}


NOTA_BASE = ("Los datos base ya incluyen los 9 errores del reto (están en tests/fixtures/ANSWER_KEY.md): por eso "
             "verás hallazgos aunque no hayas alterado nada.")
NOTA_DEMO = ("Esta demostración parte de los datos base, que ya incluyen los 9 errores del reto, y suma 7 errores "
             "más (data/demo_errores/ANSWER_KEY.md).")


def render(res, props=None, demo: bool = False) -> None:
    d = calcular(res, props)
    st.caption(NOTA_DEMO if demo else NOTA_BASE)
    cel = [("Archivos leídos", f"{d['archivos_leidos']} de {d['archivos_total']}", "Los que NEXUS pudo leer con su perfil.", ""),
           ("Registros leídos", d["registros"], "Filas de todos los archivos.", ""),
           ("Correctos", d["correctos"], "Entran al consolidado tal como vienen.", ""),
           ("Corregidos automáticamente", d["auto"], "Solo duplicados exactos con el mismo ID; se pueden revertir.",
            "amber" if d["auto"] else ""),
           ("Pendientes de tu decisión", d["pendientes"],
            "Correcciones propuestas que esperan que las apruebes o rechaces, y cuentas sin confirmar.",
            "amber" if d["pendientes"] else ""),
           ("Bloqueados", d["bloqueados"], "No entran al consolidado hasta corregirse.", "red" if d["bloqueados"] else "")]
    celdas = "".join(f'<div class="nx-fig"><div class="nx-fig-l">{escape(l)}</div>'
                     f'<div class="nx-fig-v {t}">{escape(str(v))}</div><div class="nx-fig-n">{escape(n)}</div></div>'
                     for l, v, n, t in cel)
    st.markdown(f'<div class="nx-wrap"><div class="nx-strip c4" style="--cols:3">{celdas}</div></div>',
                unsafe_allow_html=True)
    filas = "".join(
        f'<div class="nx-row"><span class="nx-dot { {"rojo": "red", "amarillo": "amber", "verde": "green"}[a["estado"]] }"></span>'
        f'<div><div class="nx-row-t">{escape(a["nombre"])}</div>'
        f'<div class="nx-row-s">{escape(a["archivo"])}: {a["registros"]} registros, {a["correctos"]} correctos. '
        f'{escape(a["motivo"])}. Huella (SHA-256): {escape(a["huella"][:16])}…</div></div>'
        f'<span class="nx-state { {"rojo": "red", "amarillo": "amber", "verde": "green"}[a["estado"]] }">'
        f'{ {"rojo": "Rojo", "amarillo": "Amarillo", "verde": "Verde"}[a["estado"]] }</span></div>' for a in d["archivos"])
    st.markdown('<div class="nx-list">' + filas + "</div>", unsafe_allow_html=True)
    st.caption("Verde: sin observaciones. Amarillo: algo espera tu decisión o se corrigió solo. Rojo: hay registros "
               "bloqueados, un mes faltante o el archivo no se pudo leer.")
