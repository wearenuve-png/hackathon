"""Contexto que se envia al modelo: SOLO un resumen ya calculado del escenario y periodo actuales.

Incluye cifras consolidadas, hallazgos con sus fichas, variaciones y causas, nivel de confianza y el estado de los
archivos con su huella. NUNCA incluye archivos fuente ni filas crudas (no hay Record.raw, ni descripciones, ni
contrapartes en texto libre): de los registros solo viajan ubicaciones (archivo, hoja, fila) de los hallazgos."""
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from nexus import metrics, variance
from nexus.confidence import confidence
from nexus.diagnostico import NOMBRES, diagnosticar
from nexus.limitaciones import LIMITACIONES
from nexus.ui import correcciones, resumen_carga

PESTANAS = {
    "Resumen": "Resumen de la carga, cifras del encabezado, qué falta para cerrar y nivel de confianza.",
    "Estados financieros": "Estado de resultados y balance consolidados en USD, y el detalle por cuenta.",
    "Alertas y errores": "Alertas, registros fuera del consolidado y la sección Hallazgos con una ficha por hallazgo.",
    "Intercompañía": "Operaciones entre empresas que cuadran (se eliminan) y las que no cuadran (no se eliminan).",
    "Trazabilidad": "De cada cifra al archivo, la hoja y la fila de donde sale, con tasa y ajustes.",
    "Indicadores": "ROIC, ROCE y EVA mensuales con sus supuestos.",
    "Variaciones": "Por qué cambió cada cifra frente al período anterior, con causas que suman el total.",
    "Simulador": "Efecto de mover la tasa de MXN o GTQ entre -10 % y +10 % (SIMULACIÓN).",
    "Perfiles e integridad": "Cómo se lee cada archivo, versión y aprobación del perfil, y el SHA-256 de cada archivo.",
    "Ayuda": "Glosario, preguntas frecuentes y lo que FinaCore no puede detectar.",
}
NOTA_CARGA = ("Estos datos vienen de las carpetas que la persona eligió; los errores los detectó el motor al leer "
              "esos archivos.")


def _m(d) -> str:
    return f"{Decimal(d).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):,.2f}"


def construir_contexto(res, period: str, escenario: str, demo: bool = False, props: Optional[list] = None,
                       nota: Optional[str] = None) -> dict:
    cfg = res.config
    pr = res.periods[period]
    props = props if props is not None else correcciones.proponer(res)
    prop_por_regla = {}
    for p in props:
        prop_por_regla.setdefault((p.rule_id, p.company_id, p.period), p)
    s, n = pr.summary, pr.naive_summary
    claves = ("ingresos", "costo_ventas", "gastos_operativos", "ebit", "gastos_financieros", "impuestos",
              "utilidad_neta", "activo_total", "pasivo_total", "patrimonio")
    ctx = {
        "escenario": escenario, "periodo": period, "tipo_periodo": pr.kind,
        "nota_escenario": nota if nota is not None else NOTA_CARGA,
        "estado_periodo": {"provisional": pr.provisional, "razones": list(pr.provisional_reasons),
                           "rango_utilidad_neta_usd": [_m(pr.utility_range[0]), _m(pr.utility_range[1])]
                           if pr.utility_range else None,
                           "empresas_sin_datos": list(pr.missing_companies)},
        "cifras": {"pestana": "Estados financieros (y encabezado)",
                   "consolidado_usd": {k: _m(s[k]) for k in claves},
                   "suma_de_empresas_sin_eliminar_usd": {k: _m(n[k]) for k in claves},
                   "activo_menos_pasivo_y_patrimonio_usd": _m(s["activo_menos_pasivo_y_patrimonio"])},
        "cuentas": {"pestana": "Estados financieros → Detalle por cuenta",
                    "lista": [{"codigo": c, "nombre": cfg.catalog[c].name, "consolidado_usd": _m(ln.amount_usd)}
                              for c, ln in pr.lines.items() if ln.amount_usd != 0]},
    }
    ms = [x for x in res.matches if x.period == period]
    unicas = {}
    for x in ms:
        unicas.setdefault((x.seller_id, x.buyer_id, x.reference), []).append(x)
    ctx["intercompania"] = {
        "pestana": "Intercompañía",
        "operaciones_que_cuadran": len({k for k, v in unicas.items() if all(x.status == "RECONCILED" for x in v)}),
        "operaciones_que_no_cuadran": [{"vendedor": k[0], "comprador": k[1], "referencia": k[2],
                                        "diferencia_usd": _m(abs(v[0].difference_usd)),
                                        "estado": v[0].status}
                                       for k, v in unicas.items() if any(x.status != "RECONCILED" for x in v)]}
    c = confidence(res, period)
    ctx["nivel_de_confianza"] = {"pestana": "Resumen", "nivel": c.nivel, "registros_limpios": c.limpios,
                                 "registros_total": c.total, "bloqueados": c.bloqueados, "pendientes": c.pendientes,
                                 "duplicados_excluidos": c.duplicados, "motivos_provisional": list(c.motivos)}
    carga = resumen_carga.calcular(res, [p for p in props if p.aprobable])
    ctx["archivos"] = {"pestana": "Resumen → Resumen de la carga; Perfiles e integridad",
                       "leidos": carga["archivos_leidos"], "total": carga["archivos_total"],
                       "registros_leidos": carga["registros"], "correctos": carga["correctos"],
                       "corregidos_automaticamente": carga["auto"], "bloqueados": carga["bloqueados"],
                       "pendientes_de_decision": carga["pendientes"],
                       "lista": [{"empresa": a["empresa"], "nombre": a["nombre"], "archivo": a["archivo"],
                                  "formato": cfg.profiles[a["empresa"]].source.type.upper() if a["empresa"] in cfg.profiles
                                  else None, "estado": a["estado"], "observaciones": a["motivo"],
                                  "registros": a["registros"], "sha256": a["huella"]} for a in carga["archivos"]]}
    hall = []
    for f in diagnosticar(res):
        if f.period not in (None, period):
            continue
        p = prop_por_regla.get((f.rule_id, f.company_id, f.period))
        hall.append({"ficha": f.ficha_id, "pestana": "Alertas y errores → Hallazgos", "tipo": NOMBRES[f.tipo],
                     "regla": f.rule_id, "empresa": f.company_id, "periodo": f.period,
                     "impacto_usd": None if f.impacto_usd is None else _m(f.impacto_usd),
                     "que_paso": f.que_paso,
                     "donde": [{"archivo": u.file, "hoja": u.sheet, "fila": u.row} for u in f.donde][:6],
                     "por_que_importa": f.por_que_importa, "impacto_utilidad": f.impacto_utilidad,
                     "causa_probable": f.causa_probable, "accion_recomendada": f.accion,
                     "accion_de_nexus": None if p is None else p.accion,
                     "propuesta": None if p is None or p.valor_propuesto is None else
                     {"valor_leido": p.valor_leido, "valor_propuesto": str(p.valor_propuesto), "motivo": p.motivo,
                      "es_estimacion": p.estimacion}})
    ctx["hallazgos"] = hall
    ps = sorted(res.periods)
    i = ps.index(period)
    if i > 0:
        rep = variance.compare(variance.view(res, period), variance.view(res, ps[i - 1]))
        if not rep.blocked and rep.total is not None:
            ctx["variaciones"] = {
                "pestana": "Variaciones", "contra_periodo": ps[i - 1], "utilidad_neta": rep.total.phrase,
                "causas_de_la_utilidad_usd": {variance.CAUSE_NAMES[k]: variance.sfmt(v)
                                              for k, v in rep.total.causes.items() if v != 0 or k == variance.SIN},
                "cuentas_materiales": [v.phrase for v in sorted((v for v in rep.by_account.values() if v.material),
                                                                key=lambda v: -abs(v.total))][:5]}
    else:
        ctx["variaciones"] = None
    ind = metrics.compute_indicators(res, period)
    ctx["indicadores_mensuales"] = {
        "pestana": "Indicadores", "ROIC": None if ind.roic is None else f"{ind.roic:.2%}",
        "ROCE": None if ind.roce is None else f"{ind.roce:.2%}", "EVA_usd": None if ind.eva is None else _m(ind.eva),
        "supuestos": "WACC, tasa de impuesto y definición de capital son SUPUESTO del equipo, no datos del reto."}
    top = max(((c, ln) for c, ln in pr.lines.items() if ln.record_ids), key=lambda t: abs(t[1].amount_usd), default=None)
    if top:
        r0 = next(r for r in res.records if r.record_id == top[1].record_ids[0])
        ctx["ejemplo_trazabilidad"] = {"pestana": "Trazabilidad", "cuenta": top[0], "nombre": cfg.catalog[top[0]].name,
                                       "consolidado_usd": _m(top[1].amount_usd), "registros": len(top[1].record_ids),
                                       "primer_registro": {"archivo": r0.source_file, "hoja": r0.source_sheet,
                                                           "fila": r0.source_row}}
    else:
        ctx["ejemplo_trazabilidad"] = None
    ctx["pestanas_de_la_app"] = PESTANAS
    ctx["limitaciones_de_nexus"] = [{"id": i_, "titulo": t, "detalle": d} for i_, t, d in LIMITACIONES]
    return ctx
