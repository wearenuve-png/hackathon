"""Lo que NEXUS NO puede detectar con certeza. Una sola lista: la usan docs/VERIFICACION.md y la pestana Ayuda
(un test verifica que el documento contiene cada titulo)."""

LIMITACIONES = [
    ("L1", "Error de moneda con poco historial",
     "La sospecha de moneda equivocada (x8, /8) necesita al menos 3 periodos de la misma cuenta y empresa. Con 2 "
     "periodos o menos no hay referencia para decir cual es el atipico."),
    ("L2", "Errores presentes en todo el historial",
     "Si el error esta en todos los periodos (siempre mal), no hay comparacion que lo delate."),
    ("L3", "La hipotesis de moneda no es una certeza",
     "NEXUS propone que otra moneda explicaria el historial y muestra el impacto; dos monedas pueden encajar. "
     "Nunca corrige solo: una persona confirma."),
    ("L4", "Duplicados con datos distintos o sin historial activado",
     "Se detectan duplicados por mismo ID (confirmado), por mismo importe, fecha y contraparte (posible), por mismo "
     "ID en dos empresas y por archivos identicos (mismo SHA-256) dentro de una carga. El reenvio ENTRE ejecuciones "
     "(mismo archivo o mismos IDs en una ejecucion anterior guardada) solo se advierte si se activa el historial "
     "(run(history_dir=...) o --historial); la interfaz no lo activa por defecto. Un duplicado con otro ID, otro "
     "importe o sin contraparte no se detecta."),
    ("L5", "Cuenta mapeada pero equivocada",
     "Solo se detecta la cuenta SIN equivalencia. Una equivalencia aprobada que apunta a la cuenta equivocada pasa."),
    ("L6", "Tasa mal escrita sin salto detectable",
     "Se bloquea la tasa faltante, vacia, en 0 o no numerica, y se marca como sospechosa la que cambia mas del umbral "
     "(15 %) frente al mes anterior. No se detecta la PRIMERA tasa de una moneda (sin historial), ni una tasa mal "
     "escrita que cambie menos que el umbral, ni una deriva gradual."),
    ("L7", "Errores que se compensan",
     "Un importe equivocado que deja totales y balance cuadrados, o dos errores que se cancelan, no se detecta."),
    ("L8", "Balance solo por empresa completa",
     "La alerta de balance descuadrado exige que la empresa reporte activo, pasivo y patrimonio en el periodo."),
    ("L9", "Intercompania sin contraparte identificable",
     "Solo se concilia una operacion si la contraparte se reconoce por ID o alias del grupo. Sin contraparte, no hay "
     "conciliacion ni eliminacion."),
    ("L10", "Fecha equivocada dentro del calendario",
     "Se bloquea la fecha invalida o fuera del calendario del grupo. Una fecha valida pero en el mes equivocado no "
     "se detecta."),
    ("L11", "Moneda del archivo: umbral del 90 %",
     "La carga se bloquea si al menos el 90 % de las filas declara una moneda distinta a la del perfil. Una mezcla "
     "menor pasa y se revisa fila por fila."),
    ("L12", "Datos sinteticos",
     "Todo se probo con un grupo sintetico y errores sembrados. No hay pruebas con datos reales: los formatos reales "
     "pueden requerir perfiles nuevos."),
    ("L13", "Integridad antes de leer",
     "El SHA-256 prueba que un archivo no cambio DESPUES de leerlo. No detecta que alguien lo haya alterado antes, "
     "ni controla accesos o identidades."),
    ("L14", "Alias de moneda no soportado",
     "Un codigo como «Q» se reconoce como probable alias de GTQ en la ficha de diagnostico, pero los perfiles hoy no "
     "admiten alias de moneda: el registro queda bloqueado y la via es corregir el archivo de origen."),
    ("L15", "El diagnostico de balance es una heuristica",
     "Las causas candidatas de un balance descuadrado (registro igual a D, importe x 2, duplicado, registros fuera de "
     "balance, diferencia de tasa) son coincidencias numericas, no pruebas: pueden ser casuales o faltar la real. Se "
     "calcula por empresa y periodo."),
]
