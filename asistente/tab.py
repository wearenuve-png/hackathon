"""Pestaña «Asistente» (prototipo). Modo conectado solo si existe ANTHROPIC_API_KEY; si no, modo local con 6 preguntas
sugeridas respondidas con plantillas. Nunca se muestra un error tecnico al usuario."""
import streamlit as st

from . import cliente, local
from .config import cargar_config
from .contexto import construir_contexto

ETIQUETA_CONECTADO = ("Asistente NEXUS (prototipo) · impulsado por un modelo de lenguaje · responde solo con los datos "
                      "de esta pantalla · modo conectado")
ETIQUETA_LOCAL = ("Asistente NEXUS (prototipo) · modo local: sin modelo de lenguaje, respuestas con plantillas a partir "
                  "de los resultados de esta pantalla")
AVISO_FALLBACK = ("No pude consultar al modelo en este momento. Te muestro las preguntas sugeridas del modo local, "
                  "que no necesitan red.")


def _local(ctx: dict):
    st.markdown("**Modo local: preguntas sugeridas**")
    cols = st.columns(3)
    for i, (clave, texto) in enumerate(local.PREGUNTAS):
        if cols[i % 3].button(texto, key=f"asist_local_{clave}", use_container_width=True):
            st.session_state["asist_local"] = clave
    clave = st.session_state.get("asist_local")
    if clave:
        st.markdown(local.responder_local(clave, ctx))


def render(res, period: str, escenario: str, demo: bool = False, props=None):
    cfg = cargar_config()
    try:
        ctx = construir_contexto(res, period, escenario, demo, props)
    except Exception:  # noqa: BLE001
        st.info("El asistente no tiene resultados que mostrar en este momento.")
        return
    cli = cliente.obtener_cliente()
    if cli is None:
        st.caption(ETIQUETA_LOCAL)
        st.info("El modo conectado está apagado (no hay llave configurada). Estas preguntas se responden en tu equipo, "
                "sin red y sin modelo de lenguaje.")
        _local(ctx)
        return
    st.caption(ETIQUETA_CONECTADO)
    st.caption(f"Escenario: {escenario} · período {period}. El modelo recibe un resumen ya calculado de esta pantalla, "
               "nunca los archivos ni las filas originales. No corrige datos ni aprueba nada.")
    hist = st.session_state.setdefault("asist_hist", [])
    for m in hist:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
    q = st.chat_input("Pregunta sobre los resultados de esta pantalla")
    if q:
        with st.chat_message("user"):
            st.markdown(q)
        api = [{"role": m["role"], "content": m["content"]} for m in hist]
        try:
            ans = cliente.preguntar(cli, ctx, api, q, cfg["max_mensajes_historial"])
        except Exception:  # noqa: BLE001 - nunca se muestra el error tecnico
            ans = None
        if ans is None:
            st.warning(AVISO_FALLBACK)
            _local(ctx)
            return
        hist.append({"role": "user", "content": q})
        hist.append({"role": "assistant", "content": ans})
        del hist[:-cfg["max_mensajes_historial"]]
        with st.chat_message("assistant"):
            st.markdown(ans)
    if hist and st.button("Borrar conversación", key="asist_borrar"):
        st.session_state["asist_hist"] = []
        st.rerun()
