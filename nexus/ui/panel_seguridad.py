"""Panel «Seguridad e integridad» (dentro de la pestaña Perfiles e integridad)."""
import pandas as pd
import streamlit as st

from . import correcciones, seguridad


def render(res, data_dir, ver, n_hash_ok: int, n_hash: int) -> None:
    st.markdown("### Seguridad e integridad")
    st.caption("Detecta que un archivo o la bitácora hayan cambiado. No es una defensa contra intrusos: mira la tabla del final.")

    # a) manifiesto firmado de la ejecucion anterior
    st.markdown("**1. Archivos fuente contra el manifiesto de la ejecución anterior**")
    mp = seguridad.manifiesto_path(data_dir)
    cmp_ = seguridad.comparar_manifiesto(mp, res.input_hashes)
    if cmp_["status"] == "NUEVO":
        seguridad.guardar_manifiesto(mp, data_dir, res.input_hashes)
        st.info(f"Primera ejecución sobre esta carpeta: se guardó el manifiesto firmado con {len(res.input_hashes)} huellas. "
                "La próxima vez se compara contra él.")
    elif cmp_["status"] == "IGUAL":
        st.success(f"Sin cambios: las {len(res.input_hashes)} huellas coinciden con el manifiesto firmado "
                   f"({cmp_['manifiesto']['creado']}).")
    elif cmp_["status"] == "ALTERADO":
        st.error("El manifiesto guardado fue alterado: su firma ya no coincide. No se puede confiar en la comparación.")
    else:
        st.error(f"{len(cmp_['cambios'])} archivo(s) cambiaron sin que se declarara el cambio desde la ejecución anterior.")
        st.dataframe(pd.DataFrame([{"Archivo": c["archivo"], "Tipo": c["tipo"], "Huella anterior": c["antes"] or "-",
                                    "Huella ahora": c["ahora"] or "-"} for c in cmp_["cambios"]]),
                     width="stretch", hide_index=True)
        if st.button("Declarar estos cambios y guardar un manifiesto nuevo", key="declarar_cambios"):
            seguridad.guardar_manifiesto(mp, data_dir, res.input_hashes, anterior=cmp_["manifiesto"]["firma"])
            st.rerun()

    # b) bitacora encadenada
    st.markdown("**2. Bitácora de aprobaciones (cadena de hashes)**")
    v = seguridad.verificar_bitacora(correcciones.log_por_defecto())
    (st.success if v["ok"] else st.error)(f"{v['mensaje']} ({v['n']} registro(s))")

    # c) garantias
    st.markdown("**3. Estado de las garantías**")
    st.dataframe(pd.DataFrame(seguridad.garantias(n_hash_ok, n_hash)), width="stretch", hide_index=True)

    # d) alcance honesto
    st.markdown("**4. Qué protege / Qué NO protege**")
    st.dataframe(pd.DataFrame(seguridad.TABLA_ALCANCE, columns=["Qué protege", "Qué NO protege"]),
                 width="stretch", hide_index=True)
