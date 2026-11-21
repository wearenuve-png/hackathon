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
    ("L4", "Duplicados con datos distintos o en otra carga",
     "Solo se detectan duplicados por mismo ID (confirmado), por mismo importe, fecha y contraparte (posible), por "
     "mismo ID en dos empresas y por archivos identicos (mismo SHA-256) dentro de una misma carga. Un duplicado con "
     "otro ID o importe, o el reenvio de un archivo en otra ejecucion, no se detecta."),
    ("L5", "Cuenta mapeada pero equivocada",
     "Solo se detecta la cuenta SIN equivalencia. Una equivalencia aprobada que apunta a la cuenta equivocada pasa."),
    ("L6", "Tipo de cambio incorrecto pero mayor que cero",
     "Se bloquea la tasa faltante, vacia, en 0 o no numerica. Una tasa mal escrita (0.5 en vez de 0.05) no se "
     "detecta: no hay validacion de rango de tasas."),
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
]
