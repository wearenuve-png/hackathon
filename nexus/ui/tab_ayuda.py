"""Pestana Ayuda: glosario y preguntas frecuentes ESTATICAS. No hay chatbot ni IA."""
import streamlit as st

from ..limitaciones import LIMITACIONES

GLOSARIO = [
    ("PROVISIONAL",
     "Un periodo es PROVISIONAL cuando hay algo sin resolver que podria cambiar sus cifras: registros bloqueados o "
     "pendientes, una empresa que no entrego el mes, una discrepancia intercompania abierta o una alerta de revision. "
     "Las cifras se muestran igual, pero no son definitivas hasta resolver esos puntos."),
    ("Discrepancia intercompañía",
     "Una empresa del grupo dice haber vendido X a otra, y la otra dice haber comprado Y. Si X e Y no coinciden "
     "dentro de la tolerancia, NEXUS abre una discrepancia y NO elimina ninguno de los dos lados: eliminar a ciegas "
     "taparia un error. Se concilia con las empresas y se corrige el archivo."),
    ("De una cifra a su registro",
     "En la pestaña Trazabilidad se elige una cifra (por ejemplo Ingresos por ventas, cuenta 4000) y se ve cada "
     "registro que la forma: empresa, archivo, hoja y fila, importe original, moneda, tasa del mes, importe en USD y "
     "los ajustes aplicados. Asi se llega desde el numero hasta la celda del archivo original."),
    ("Por qué se bloquea un registro",
     "Un registro se bloquea cuando no se puede confiar en el dato: moneda faltante o invalida, tasa de cambio "
     "ausente o en cero, importe que no es un numero, fecha invalida o fuera del calendario, o signo invertido. "
     "NO se corrige solo: queda fuera del consolidado, con su importe y su motivo, hasta que alguien corrija el archivo."),
    ("SUPUESTO",
     "Valor que decidio el equipo y que no viene de los datos: WACC, tasa de impuesto, definicion de capital, "
     "umbral de materialidad de las variaciones y la convencion de descomposicion operacion / tipo de cambio. "
     "Siempre se muestra con la etiqueta SUPUESTO y se puede cambiar sin tocar el codigo."),
    ("Sin explicar",
     "En el explicador de variaciones, la parte del cambio que los datos no prueban (por ejemplo, un registro "
     "bloqueado sin valor en USD o un cambio de moneda entre periodos). NEXUS prefiere decirlo antes que adivinar."),
    ("Rango de impacto",
     "Para un registro bloqueado que afecta la utilidad: cuanto valdria la utilidad si se excluye (como esta), si "
     "entrara tal como viene y si se corrigiera. Es informativo: ninguna cifra se modifica."),
    ("Nivel de confianza",
     "Resume cuantos registros del periodo estan limpios (entran al consolidado) frente a bloqueados o pendientes. "
     "ALTA: periodo definitivo y al menos 99 % limpio; MEDIA: al menos 95 % limpio y sin empresas faltantes; "
     "BAJA: en cualquier otro caso. Es una regla simple, no una probabilidad."),
    ("Ficha de hallazgo",
     "Cada hallazgo bloqueado o marcado tiene una ficha: que paso, donde (archivo, hoja y fila), por que importa "
     "(impacto en USD y en la utilidad), la causa PROBABLE y la accion humana recomendada. La causa siempre es una "
     "hipotesis y nunca se atribuye a una persona; NEXUS no corrige ni convierte nada por su cuenta."),
    ("Diagnóstico de balance descuadrado",
     "Cuando activo no es igual a pasivo + patrimonio por una diferencia D, NEXUS busca en orden causas candidatas: "
     "un registro con importe igual a D, un registro cuyo importe x 2 es D (signo invertido), un duplicado por D, "
     "registros bloqueados o pendientes que suman D, o una diferencia de tasa. Si ninguna coincide, dice 'causa no "
     "identificada' y muestra los registros mas cercanos. Son coincidencias numericas, no pruebas."),
    ("Tasa sospechosa",
     "Una tasa de cambio que cambia mas de un umbral (15 % por defecto, configurable) frente al mes anterior, por "
     "ejemplo 0.05 que pasa a 0.5. Se marca con su impacto en USD y se pide confirmacion; no se bloquea ni se corrige."),
    ("Posible reenvío",
     "El mismo archivo (mismo SHA-256) o los mismos IDs de transaccion ya cargados en una ejecucion anterior. Solo "
     "advierte, con la fecha de la ejecucion previa; requiere activar el historial."),
    ("SIMULACIÓN",
     "El simulador recalcula en memoria el consolidado y los indicadores con una tasa distinta (-10 % a +10 %). "
     "No cambia datos, tasas ni archivos."),
]

FAQ = [
    ("¿Los datos son reales?",
     "No: son datos sinteticos de un grupo ficticio con errores sembrados a proposito."),
    ("¿Que pasa si una empresa cambia el formato de su archivo?",
     "Su carga queda en REVISION con el motivo (por ejemplo, falta un encabezado) y no se procesa nada en silencio. "
     "Se corrige actualizando y aprobando su perfil."),
    ("¿Los numeros los calcula una IA?",
     "No. Todo es calculo determinista con Decimal. No hay chatbot ni IA en NEXUS."),
    ("¿Se modifican mis archivos?",
     "No. Se leen en solo lectura; el SHA-256 de cada archivo se registra al leer y se vuelve a comprobar."),
]


def render() -> None:
    st.subheader("Ayuda")
    st.caption("Glosario y preguntas frecuentes. Contenido fijo: no hay chatbot.")
    st.markdown("### Glosario")
    for termino, texto in GLOSARIO:
        with st.expander(termino):
            st.markdown(texto)
    st.markdown("### Preguntas frecuentes")
    for q, a in FAQ:
        with st.expander(q):
            st.markdown(a)
    st.markdown("### Qué NO puede detectar NEXUS")
    st.caption("No prometemos detectar todo error. Estas son las limitaciones conocidas (detalle en "
               "docs/VERIFICACION.md).")
    for id_, titulo, detalle in LIMITACIONES:
        with st.expander(f"{id_}. {titulo}"):
            st.markdown(detalle)
