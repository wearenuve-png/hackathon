"""Seccion 'Demostracion de errores' (dentro de Alertas y errores). Aplica un error a una COPIA temporal de los datos,
corre el pipeline en la copia y muestra el balance descuadrado con su ficha de diagnostico. Los datos reales, los
archivos originales y el resto de la app no cambian."""
import pandas as pd
import streamlit as st

from . import demo_error as DE
from .tab_hallazgos import mostrar_ficha

REALES = "Datos reales"
NOMBRE_CAUSA = {"REGISTRO_IGUAL_A_D": "registro con importe igual al desbalance (asiento omitido o sobrante)",
                "SIGNO_INVERTIDO": "signo invertido (importe × 2 = desbalance)",
                "DUPLICADO": "duplicado por el importe del desbalance"}


def _m(d):
    return f"{d:,.2f}"


def _volver():
    est = st.session_state.pop("demo_estado", None)
    if est:
        DE.limpiar(est[1].tmp_dir)
    st.session_state["demo_caso"] = REALES


def render(res, periodo, data_dir, profiles_dir) -> None:
    st.markdown('<div class="nx-h">Demostración de errores</div>', unsafe_allow_html=True)
    st.caption("Elige un error para ver cómo lo detecta NEXUS. Se aplica a una copia temporal de los datos: los "
               "archivos originales y la carpeta de datos no se tocan, y el resto de la app sigue con los datos reales.")
    et = DE.etiquetas()
    sel = st.selectbox("Demostración de errores", [REALES] + list(et.values()), key="demo_caso")
    est = st.session_state.get("demo_estado")
    if sel == REALES:
        if est:
            DE.limpiar(est[1].tmp_dir)
            st.session_state.pop("demo_estado", None)
        st.caption("Estás viendo los datos reales.")
        return
    caso = next(k for k, v in et.items() if v == sel)
    clave = (caso, str(data_dir), str(profiles_dir))
    if est is None or est[0] != clave:
        if est:
            DE.limpiar(est[1].tmp_dir)
        try:
            est = (clave, DE.correr(DE.preparar(caso, data_dir, profiles_dir)))
        except Exception as e:  # noqa: BLE001 - se explica, no se rompe la app
            st.session_state.pop("demo_estado", None)
            st.warning(f"La demostración no está disponible con esta fuente de datos: {e}")
            return
        st.session_state["demo_estado"] = est
    d = est[1]

    st.error(DE.BANNER, icon=":material/science:")
    st.button("Volver a los datos reales", key="demo_volver", on_click=_volver)
    st.markdown(f"**{d.titulo}.** {d.descripcion}")
    st.caption(f"Empresa {d.company_id}, período {d.period}. Se agregaron estas filas al archivo {d.extras['archivo']} "
               f"de la copia temporal: " + "; ".join(d.filas) + ".")
    if d.period != periodo:
        st.caption(f"La demostración siempre usa el período {d.period}; no depende del período elegido arriba.")

    s = d.run.periods[d.period].summary
    st.dataframe(pd.DataFrame([{"Concepto": "Activo total", "USD (copia alterada)": _m(s["activo_total"])},
                               {"Concepto": "Pasivo total", "USD (copia alterada)": _m(s["pasivo_total"])},
                               {"Concepto": "Patrimonio", "USD (copia alterada)": _m(s["patrimonio"])}]),
                 width="stretch", hide_index=True)
    st.error(f"Balance descuadrado: Activo − (Pasivo + Patrimonio) = {_m(s['activo_menos_pasivo_y_patrimonio'])} USD "
             f"(en los datos reales es 0.00).")

    f = DE.ficha_para_demo(d)
    if f is None:
        st.error("NEXUS no generó la ficha de balance para este caso.")
        return
    nombre = NOMBRE_CAUSA[d.esperado]
    if d.detectada:
        st.success(f"Causa esperada de este caso: {nombre}. Detectada como candidata n.º {d.candidata_orden} del motor.")
    else:
        st.error(f"Causa esperada de este caso: {nombre}. NO fue detectada.")
    st.caption("Aquí se muestra primero la causa candidata que corresponde al caso; el número de cada candidata es su "
               "orden determinista en el motor (no se renumera). Son coincidencias numéricas, no pruebas.")
    mostrar_ficha(f)
