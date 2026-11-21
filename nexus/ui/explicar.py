"""'Explicar todo en simple': el recorrido de la carga, paso a paso, con los numeros reales de esta ejecucion."""
from decimal import ROUND_HALF_UP, Decimal
from typing import List, Tuple

import streamlit as st

from ..schemas import BLOCKED, EXCLUDED_DUPLICATE, OK, PENDING_MAPPING


def m(d) -> str:
    return f"{Decimal(d).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):,.2f}"


def pasos(res, period: str, props=None) -> List[Tuple[str, str]]:
    cfg, pr = res.config, res.periods[period]
    props = props or []
    leidos = [r for r in res.load_reports.values() if r.status != "REVIEW"]
    formatos = sorted({p.source.type.upper() for p in cfg.profiles.values()}) or ["detección automática"]
    n_regs = sum(r.n_records for r in leidos)
    revision = [r.company_id for r in res.load_reports.values() if r.status == "REVIEW"]
    s1 = (f"NEXUS abrió los archivos de {len(cfg.companies)} empresas, en solo lectura (no cambia ni una celda). "
          f"Leyó {len(leidos)} y obtuvo {n_regs} registros. Formatos: {', '.join(formatos)}."
          + (f" No pudo leer {', '.join(revision)}: su archivo no coincide con su perfil." if revision else ""))
    s2 = ("Cada empresa escribe distinto (otras columnas, otros nombres de cuenta, otra moneda). Con el perfil de cada "
          "una, NEXUS lo pasa todo a una misma tabla: empresa, período, cuenta del catálogo común, importe, moneda, y de "
          "qué archivo, hoja y fila salió. Las cuentas que no reconoce no las adivina: quedan pendientes.")
    bloq = sum(1 for e in pr.excluded if e.status == BLOCKED)
    pend = sum(1 for e in pr.excluded if e.status == PENDING_MAPPING)
    dup = sum(1 for e in pr.excluded if e.status == EXCLUDED_DUPLICATE)
    n_find = len([f for f in res.findings if f.period in (None, period)])
    s3 = (f"Se revisa cada registro: importes que no son número, signos al revés, monedas raras, fechas fuera del período, "
          f"duplicados, totales y balances que no cuadran, tasas sospechosas. En {period} hubo {n_find} hallazgos: "
          f"{bloq} registro(s) bloqueado(s), {pend} con cuenta sin confirmar y {dup} duplicado(s) que NEXUS excluyó solo "
          f"con un ajuste reversible. Lo bloqueado no entra al consolidado; "
          f"{len([p for p in props if p.aprobable])} corrección(es) esperan tu decisión.")
    ej = next((r for r in res.records if r.period == period and r.status == OK and r.currency not in (None, "USD")
               and r.amount_usd is not None and r.amount_original), None)
    s4 = ("Cada importe se pasa a dólares con la tasa del mes: importe × tasa."
          + (f" Por ejemplo, {m(ej.amount_original)} {ej.currency} × {ej.fx_rate} = {m(ej.amount_usd)} USD "
             f"({ej.company_id}, {ej.account_local})." if ej else "")
          + " Si falta la tasa o es cero, el registro se bloquea en vez de asumir un valor.")
    ms = [x for x in res.matches if x.period == period]
    ok = {(x.seller_id, x.buyer_id, x.reference) for x in ms if x.status == "RECONCILED"}
    mal = {(x.seller_id, x.buyer_id, x.reference) for x in ms if x.status != "RECONCILED"}
    s5 = (f"Las empresas del grupo se venden entre sí; si se sumara todo, esas ventas se contarían dos veces. NEXUS "
          f"empareja cada venta con la compra de la otra empresa: {len(ok)} operaciones cuadran y se eliminan; "
          f"{len(mal)} no cuadran y NO se eliminan (quedan abiertas para conciliar).")
    s = pr.summary
    s6 = (f"Con todo lo anterior se suman las empresas en dólares: ingresos de {m(s['ingresos'])} USD y utilidad neta de "
          f"{m(s['utilidad_neta'])} USD en {period}. "
          + ("El período está PROVISIONAL: " + "; ".join(pr.provisional_reasons) + "."
             if pr.provisional else "El período está completo.")
          + " Cada cifra se puede abrir hasta el archivo, la hoja y la fila de donde salió.")
    return [("1. Lectura", s1), ("2. Normalización", s2), ("3. Validación", s3), ("4. Conversión a USD", s4),
            ("5. Eliminaciones entre empresas", s5), ("6. Consolidación", s6)]


def render(res, period, props=None) -> None:
    if st.button("Explicar todo en simple", key="explicar_btn"):
        st.session_state["explicar_on"] = not st.session_state.get("explicar_on", False)
    if st.session_state.get("explicar_on"):
        with st.container(border=True):
            st.markdown("**Qué hizo NEXUS con tus archivos, paso a paso**")
            for titulo, texto in pasos(res, period, props):
                st.markdown(f"**{titulo}.** {texto}")
