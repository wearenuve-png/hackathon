"""Modo local: 6 preguntas sugeridas respondidas con PLANTILLAS a partir del contexto ya calculado. Sin red, sin modelo."""
from typing import Dict, List, Tuple

PREGUNTAS: List[Tuple[str, str]] = [
    ("archivos", "¿Qué archivos leyó NEXUS?"),
    ("errores", "¿Qué errores encontró?"),
    ("utilidad", "¿Por qué cambió la utilidad?"),
    ("provisional", "¿Qué significa PROVISIONAL?"),
    ("cifra", "¿Cómo llego de una cifra a su registro?"),
    ("limites", "¿Qué no detecta NEXUS?"),
]
ESTADO = {"rojo": "rojo", "amarillo": "amarillo", "verde": "verde"}


def _archivos(c: dict) -> str:
    a = c["archivos"]
    lineas = [f"NEXUS leyó **{a['leidos']} de {a['total']}** archivos y obtuvo **{a['registros_leidos']}** registros "
              f"({a['correctos']} correctos, {a['bloqueados']} bloqueados, {a['corregidos_automaticamente']} corregidos "
              f"automáticamente). Fuente: pestaña *Resumen → Resumen de la carga*.", ""]
    for f in a["lista"]:
        lineas.append(f"- **{f['nombre']}** ({f['archivo']}, {f['formato'] or 'detección automática'}): "
                      f"{ESTADO[f['estado']]}, {f['registros']} registros. {f['observaciones'].capitalize()}. "
                      f"SHA-256: `{f['sha256'][:16]}…`")
    lineas += ["", "Las huellas completas están en *Perfiles e integridad*. Los archivos se leen en solo lectura."]
    return "\n".join(lineas)


def _errores(c: dict) -> str:
    h = c["hallazgos"]
    if not h:
        return "En este período no hay hallazgos (pestaña *Alertas y errores → Hallazgos*)."
    por: Dict[str, int] = {}
    for x in h:
        por[x["tipo"]] = por.get(x["tipo"], 0) + 1
    lineas = [f"En {c['periodo']} hay **{len(h)} hallazgo(s)**: " + ", ".join(f"{n} de tipo «{t}»"
                                                                          for t, n in sorted(por.items())) + ".", ""]
    for x in h[:8]:
        imp = f" (impacto {x['impacto_usd']} USD)" if x["impacto_usd"] else ""
        lineas.append(f"- **{x['ficha']}** · {x['tipo']} · {x['empresa'] or 'Grupo'}{imp}: {x['que_paso']}")
    if len(h) > 8:
        lineas.append(f"- … y {len(h) - 8} más.")
    lineas += ["", "Cada uno tiene su ficha (qué pasó, dónde, por qué importa, causa probable y qué decidir) en la pestaña "
               "*Alertas y errores → Hallazgos*. " + c["nota_escenario"]]
    return "\n".join(lineas)


def _utilidad(c: dict) -> str:
    v = c["variaciones"]
    u = c["cifras"]["consolidado_usd"]["utilidad_neta"]
    if not v:
        return (f"{c['periodo']} es el primer período: no hay un período previo con el cual comparar, así que no puedo "
                f"decir por qué cambió. La utilidad neta consolidada es **{u} USD** (pestaña *Estados financieros*). "
                f"Elige un período posterior para ver la comparación en la pestaña *Variaciones*.")
    lineas = [f"{v['utilidad_neta']}", "", "Causas (pestaña *Variaciones*, suman exacto el total):"]
    lineas += [f"- {k}: {val} USD" for k, val in v["causas_de_la_utilidad_usd"].items()]
    lineas += ["", "Si aparece «Sin explicar», es la parte que los datos no prueban: NEXUS prefiere decirlo antes que adivinar."]
    return "\n".join(lineas)


def _provisional(c: dict) -> str:
    e = c["estado_periodo"]
    base = ("**PROVISIONAL** significa que el período todavía tiene algo sin resolver que podría cambiar sus cifras: "
            "registros bloqueados o pendientes, una empresa que no entregó datos, una diferencia entre empresas abierta o "
            "una alerta de revisión. Las cifras se muestran igual, pero no son definitivas.")
    if not e["provisional"]:
        return base + f"\n\n{c['periodo']} está **completo**: no hay nada pendiente."
    razones = "\n".join(f"- {r}" for r in e["razones"])
    rango = (f"\n\nLa utilidad neta puede quedar entre {e['rango_utilidad_neta_usd'][0]} y "
             f"{e['rango_utilidad_neta_usd'][1]} USD al resolver lo pendiente." if e["rango_utilidad_neta_usd"] else "")
    return f"{base}\n\nPor qué {c['periodo']} es PROVISIONAL (pestaña *Resumen*):\n{razones}{rango}"


def _cifra(c: dict) -> str:
    t = c["ejemplo_trazabilidad"]
    ej = ""
    if t:
        r = t["primer_registro"]
        ej = (f"\n\nEjemplo: la cuenta {t['cuenta']} «{t['nombre']}» vale {t['consolidado_usd']} USD y sale de "
              f"{t['registros']} registro(s); el primero está en el archivo `{r['archivo']}`, hoja "
              f"{r['hoja'] or '-'}, fila {r['fila']}.")
    return ("Ve a la pestaña **Trazabilidad**, elige una cifra (por ejemplo «Ingresos por ventas (cuenta 4000)») y verás cada "
            "registro que la forma: empresa, archivo, hoja y fila, importe original, moneda, tasa del mes, importe en USD "
            "y los ajustes aplicados (como las eliminaciones entre empresas)." + ej)


def _limites(c: dict) -> str:
    lineas = ["NEXUS no promete detectar «todo error». Lo que **no** puede detectar con certeza (detalle en la pestaña "
              "*Ayuda* y en `docs/VERIFICACION.md`):", ""]
    lineas += [f"- **{x['id']}. {x['titulo']}**: {x['detalle']}" for x in c["limitaciones_de_nexus"]]
    return "\n".join(lineas)


RESPUESTAS = {"archivos": _archivos, "errores": _errores, "utilidad": _utilidad, "provisional": _provisional,
              "cifra": _cifra, "limites": _limites}


def responder_local(clave: str, ctx: dict) -> str:
    return RESPUESTAS[clave](ctx)
