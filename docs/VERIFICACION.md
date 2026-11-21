# Matriz de verificación de errores

Cada caso tiene una prueba con **datos mínimos** (1 o 2 empresas y pocas filas, armadas en una carpeta temporal con
sus perfiles) en [`tests/test_matriz_errores.py`](../tests/test_matriz_errores.py). Los valores se calculan a mano
dentro de cada prueba. Datos **sintéticos**: ver la limitación L12.

Estados: **probado** = existe la prueba y pasa; **probado con límite** = pasa, pero tiene una limitación
documentada abajo.

## Matriz

| # | Caso | Qué hace NEXUS | Estado | Qué ve el usuario | Prueba |
|---|---|---|---|---|---|
| 1 | Mismo ID de transacción duplicado en un archivo | Excluye la segunda fila con un ajuste registrado, con motivo y regla, **reversible**. El original no se borra. | probado | Fila en «Registros fuera del consolidado» (`EXCLUDED_DUPLICATE`); hallazgo `DUP-01`; el consolidado la cuenta una sola vez. | `caso01` |
| 2a | Mismo archivo reenviado con otro nombre (mismo SHA-256) | Advierte; no excluye nada. | probado con límite (L4) | Alerta `ARC-01` con los dos nombres de archivo. | `caso02a` |
| 2b | Mismo ID en archivos de empresas distintas, sin ser intercompañía | Advierte y marca como posible duplicado; ambos siguen en el consolidado. | probado con límite (L4) | Alerta `DUP-03` con las empresas implicadas. | `caso02b` |
| 3 | Posible duplicado sin ID (mismo importe, fecha y contraparte) | Solo marca; **no** excluye ni ajusta. Queda pendiente de confirmación humana. | probado | Alerta `DUP-02`; bandera `POSSIBLE_DUPLICATE`. | `caso03` |
| 4 | El archivo declara USD pero el perfil dice GTQ o MXN | Bloquea la carga de esa empresa y la deja en **revisión**: no procesa ni corrige nada. Un registro suelto en otra moneda no bloquea el archivo. | probado con límite (L11) | Perfil: «EN REVISIÓN»; motivo «El archivo declara USD pero el perfil de la empresa dice GTQ»; alerta `CARGA-01`; el período queda PROVISIONAL (empresa faltante). | `caso04`, `caso04b` |
| 5 | Magnitud sospechosa frente al histórico (×8 o ÷8) | Marca un **posible error de moneda**; **no corrige**. Muestra el importe como cada moneda y el efecto en utilidad si fuera la otra. | probado con límite (L1, L2, L3) | Alerta `ATI-01`: «Como GTQ: 12,000.00 USD \| como USD: 96,000.00 USD. Efecto en utilidad si fuera GTQ: +84,000.00 USD»; período PROVISIONAL. | `caso05a`, `05b`, `05c` |
| 6 | Moneda desconocida o vacía | Bloquea el registro; no infiere la moneda. | probado | Registro `BLOCKED` con motivo; hallazgo `MON-01`; importe USD «n/c». | `caso06` |
| 7 | Tipo de cambio faltante, vacío, en 0 o no numérico | Bloquea el registro (nunca asume tasa 1 ni 0). Si la moneda no tiene **ninguna** tasa, la carga queda en revisión. | probado con límite (L6) | Motivo «Sin tasa…» o «Tasa inválida (0)…»; hallazgo `MON-01`. | `caso07`, `caso07b` |
| 8 | Columnas renombradas o faltantes | Bloquea la carga de esa empresa y la deja en revisión; nada se procesa en silencio. | probado | Perfil «EN REVISIÓN» con los encabezados que faltan; alerta `CARGA-01`. | `caso08`, `caso08b` |
| 9a | Signo invertido | Bloquea el registro (no lo corrige). | probado | `BLOCKED`, hallazgo `SIGN-01`, rango de impacto en utilidad. | `caso09a` |
| 9b | Fecha fuera de período / fecha inválida | Bloquea el registro; nunca lo reubica. | probado con límite (L10) | `BLOCKED` con «fuera del calendario del grupo» (`FEC-01`) o «Periodo inválido». | `caso09b` |
| 9c | Cuenta sin mapear | Deja el registro pendiente de confirmación; fuera del consolidado. | probado con límite (L5) | `PENDING_MAPPING`, hallazgo `MAP-01`. | `caso09c` |
| 9d | Texto o vacío en campo numérico | Bloquea el registro. | probado | `BLOCKED`: «Importe no numérico o vacío». | `caso09d` |
| 10 | Diferencia intercompañía (20,000 vs 18,000) | Abre una discrepancia; **nunca elimina sola**. Ambos lados siguen en el consolidado. | probado con límite (L9) | Alerta `IC-01` y tabla de discrepancias (2,000 USD); PROVISIONAL. | `caso10` |
| 11 | Balance descuadrado | Alerta por empresa y período (en USD); no modifica cifras. | probado con límite (L8) | Alerta `BAL-01` con activo, pasivo + patrimonio y la diferencia. | `caso11`, `caso11b` |

## Reglas agregadas en esta fase
`ARC-01` (mismo SHA-256 en dos archivos), `DUP-03` (mismo ID en empresas distintas), `FEC-01` (período fuera del
calendario), `BAL-01` (balance descuadrado), bloqueo por moneda del archivo distinta a la del perfil, bloqueo de tasa
en 0 / vacía / no numérica, y el impacto en utilidad de `ATI-01`. Todo es aditivo: las 138 pruebas anteriores siguen
pasando y la clave de respuestas no cambió.

## Limitaciones (lo que NEXUS no puede detectar con certeza)
No prometemos detectar «todo error»: detecta los casos de la matriz, y lo siguiente **queda fuera**.

| Id | Limitación | Detalle |
|---|---|---|
| L1 | Error de moneda con poco historial | La sospecha de moneda equivocada (x8, /8) necesita al menos 3 periodos de la misma cuenta y empresa. Con 2 periodos o menos no hay referencia para decir cual es el atipico. |
| L2 | Errores presentes en todo el historial | Si el error esta en todos los periodos (siempre mal), no hay comparacion que lo delate. |
| L3 | La hipotesis de moneda no es una certeza | NEXUS propone que otra moneda explicaria el historial y muestra el impacto; dos monedas pueden encajar. Nunca corrige solo: una persona confirma. |
| L4 | Duplicados con datos distintos o en otra carga | Solo se detectan duplicados por mismo ID (confirmado), por mismo importe, fecha y contraparte (posible), por mismo ID en dos empresas y por archivos identicos (mismo SHA-256) dentro de una misma carga. Un duplicado con otro ID o importe, o el reenvio de un archivo en otra ejecucion, no se detecta. |
| L5 | Cuenta mapeada pero equivocada | Solo se detecta la cuenta SIN equivalencia. Una equivalencia aprobada que apunta a la cuenta equivocada pasa. |
| L6 | Tipo de cambio incorrecto pero mayor que cero | Se bloquea la tasa faltante, vacia, en 0 o no numerica. Una tasa mal escrita (0.5 en vez de 0.05) no se detecta: no hay validacion de rango de tasas. |
| L7 | Errores que se compensan | Un importe equivocado que deja totales y balance cuadrados, o dos errores que se cancelan, no se detecta. |
| L8 | Balance solo por empresa completa | La alerta de balance descuadrado exige que la empresa reporte activo, pasivo y patrimonio en el periodo. |
| L9 | Intercompania sin contraparte identificable | Solo se concilia una operacion si la contraparte se reconoce por ID o alias del grupo. Sin contraparte, no hay conciliacion ni eliminacion. |
| L10 | Fecha equivocada dentro del calendario | Se bloquea la fecha invalida o fuera del calendario del grupo. Una fecha valida pero en el mes equivocado no se detecta. |
| L11 | Moneda del archivo: umbral del 90 % | La carga se bloquea si al menos el 90 % de las filas declara una moneda distinta a la del perfil. Una mezcla menor pasa y se revisa fila por fila. |
| L12 | Datos sinteticos | Todo se probo con un grupo sintetico y errores sembrados. No hay pruebas con datos reales: los formatos reales pueden requerir perfiles nuevos. |
| L13 | Integridad antes de leer | El SHA-256 prueba que un archivo no cambio DESPUES de leerlo. No detecta que alguien lo haya alterado antes, ni controla accesos o identidades. |

_Esta lista se genera desde `nexus/limitaciones.py`, que también alimenta la pestaña Ayuda de la interfaz._
