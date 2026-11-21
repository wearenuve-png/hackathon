# Guion de demo NEXUS (3 a 5 minutos)
> **Navegación:** la interfaz usa un menú horizontal de secciones (Inicio, Estados, Alertas, Hallazgos, Intercompañía, Trazabilidad, Indicadores, Variaciones, Simulador, Integridad, Ayuda, Asistente); donde este guion dice «pestaña» se refiere a una sección del menú.

**Datos SINTÉTICOS** (Grupo Ferrex, generados con `data/synthetic/generate.py`). Nunca presentarlos como datos reales.
Antes de empezar: `.venv/bin/streamlit run app.py`, período **2026-10** seleccionado. Plan B si falla la app o el
proyector: `.venv/bin/python scripts/demo_respaldo.py` (corre todo sin interfaz, en menos de un segundo, imprime
las mismas cifras y exporta la evidencia a `data/output/`).

## Recorrido de demo en la interfaz (5 minutos): datos base → errores → aprobación → vuelta

**Antes de ensayar:** `.venv/bin/python scripts/reset_demo.py` (vacía el registro de aprobaciones y no toca ningún archivo
fuente) y `.venv/bin/streamlit run app.py`. El selector **Escenario** está arriba de la pantalla; empieza en **Datos base**,
período **2026-10**. Todo son datos sintéticos.

| Tiempo | Paso | Dónde |
|---|---|---|
| 0:00 – 1:30 | 1. Datos base: cifra y trazabilidad | Inicio, Estados financieros, Trazabilidad |
| 1:30 – 2:00 | 2. Cambio a datos con errores | Selector **Escenario** (arriba) |
| 2:00 – 3:30 | 3. Un error de cada tipo | Alertas y errores → Hallazgos |
| 3:30 – 4:30 | 4. Aprobar una corrección con tu nombre | Alertas y errores → Hallazgos |
| 4:30 – 5:00 | 5. Vuelta a datos base | Botón **Restablecer demostración** |

### Paso 1 · Datos base (1:30)
**Mostrar:** encabezado de octubre: **Ingresos consolidados 1,985,000.00 USD** y **Utilidad neta 359,125.00**; en *Estados
financieros*, la suma de las empresas (2,078,000.00) contra el consolidado; en *Inicio*, **Resumen de la carga**: «6 de 6»
archivos leídos y, debajo, la línea que aclara que **los datos base ya incluyen los 9 errores del reto**. Luego
*Trazabilidad* → «Ingresos por ventas (cuenta 4000)» → archivo, hoja y fila.
**Decir:** «Esta es la carga de seis empresas en seis formatos. Cada cifra se abre hasta la fila del archivo. Ojo: estos datos
base ya traen los 9 errores del reto, por eso hay hallazgos aunque no hayamos tocado nada. La cuenta 4000 son solo
ingresos por ventas; el total incluye también servicios.»

### Paso 2 · Cambio a datos con errores (0:30)
**Hacer:** en el selector de arriba, elegir **Datos con errores (demostración)**.
**Decir:** «Ahora leo otra carpeta, también en solo lectura, con 7 errores más sembrados. Mira el banner: DEMOSTRACIÓN. Los
ingresos bajan a 1,758,000 porque el archivo de Aceros Ferrex declara USD siendo una empresa en quetzales y NEXUS no lo
procesa. En el resumen: 5 de 6 archivos, uno en rojo, y varias correcciones esperando decisión.»

### Paso 3 · Un error de cada tipo (1:30)
En *Alertas y errores* → **Hallazgos**, abrir una ficha de cada tipo (qué pasó, dónde con el **valor leído**, por qué importa,
qué hizo NEXUS, qué propone y qué debe decidir una persona):
- **Aplicada automáticamente** (solo el duplicado exacto con el mismo ID): factura FAC-M-0902 de Ferrex México, excluida con
  un ajuste reversible.
- **Bloqueado con propuesta exacta**: «1O,000» (letra O) de Transportes Ferrex México en octubre → propuesta 10,000 MXN
  (500 USD).
- **ESTIMACIÓN: requiere aprobación humana**: el monto en blanco de Distribuidora Central → propuesta 41,000 GTQ (mediana del
  rubro en los otros períodos). Decir que es una referencia, no un dato.
- **Balance descuadrado** (período **2026-12**): asiento omitido de 8,000 USD en Ferrex Importaciones, con el diagnóstico de
  balance (la primera candidata es el registro igual al desbalance). Y, en el mismo período, la **tasa 0.525** en vez de
  0.0525: también una *ESTIMACIÓN* (decimal corrido); sus ~28 alertas de importe atípico están dentro de su ficha como
  consecuencias.
**Decir:** «NEXUS solo aplica solo el duplicado exacto. Todo lo demás lo bloquea o lo marca y propone; las estimaciones lo
dicen con todas las letras. Nunca atribuimos el error a una persona: la causa siempre es *probable*.»

### Paso 4 · Aprobar una corrección con nombre (1:00)
**Hacer:** escribir tu nombre en **Quién aprueba**, abrir la ficha de «1O,000» en octubre y pulsar **Aprobar corrección**.
**Mostrar:** la ficha pasa a **Resueltos** (quién, cuándo, valor leído → valor aprobado, motivo); en *Estados financieros* los
gastos operativos de octubre suben 500 USD (355,325.00) y la utilidad neta baja a **300,375.00** (antes 300,875.00); en el lateral
sigue «Archivos sin cambios: 17 de 17». Mencionar el registro `data/output/aprobaciones.jsonl` y, si hay tiempo, **Deshacer**.
**Decir:** «Aprobar no modifica el archivo: se recalcula el consolidado con la corrección y queda el registro de auditoría con
mi nombre. Sin nombre, el botón está desactivado.»

### Paso 5 · Vuelta a datos base (0:30)
**Hacer:** pulsar **Restablecer demostración** (o `scripts/reset_demo.py`).
**Decir y mostrar:** «Vacía el registro de aprobaciones y vuelve a Datos base: el ingreso consolidado vuelve a 1,985,000 y los
archivos fuente nunca cambiaron.»

> Si algo sale mal en vivo: `scripts/demo_respaldo.py` corre el recorrido sin interfaz.

---

## Recorrido por temas (guion original, 4:40 + 0:20 de cierre = 5:00)

| # | Tiempo | Paso | Dónde en la app |
|---|---|---|---|
| 1 | 0:00 – 0:20 | El problema | — |
| 2 | 0:20 – 1:00 | 6 formatos, perfiles y hashes | Pestaña **Perfiles e integridad** |
| 3 | 1:00 – 1:50 | Error bloqueado, rango de impacto, PROVISIONAL | Encabezado + pestaña **Alertas y errores** |
| 4 | 1:50 – 2:30 | Consolidado de octubre vs. suma ingenua | Pestaña **Estados financieros** |
| 5 | 2:30 – 3:00 | Discrepancia intercompañía | Período **2026-11**, **Alertas y errores** |
| 6 | 3:00 – 3:30 | Clic hasta archivo, hoja y fila | Pestaña **Trazabilidad** |
| 7 | 3:30 – 4:10 | ROIC, ROCE y EVA | Pestaña **Indicadores** |
| 8 | 4:10 – 4:40 | Una variación explicada | Pestaña **Variaciones** (2026-11 vs. 2026-10) |
| — | 4:40 – 5:00 | Cierre y hoja de ruta | — |

> **Nota paso 7:** la pestaña *Indicadores* (`nexus/ui/tab_indicadores.py`) ya está conectada en `app.py`. Plan B:
> `scripts/demo_respaldo.py` (paso 7).
>
> **Nota paso 8:** el explicador (`nexus/variance.py`, pestaña *Variaciones*) está construido. Con plantillas, sin
> IA, descompone la variación en causas que suman exacto el total y muestra «Sin explicar» cuando los datos no
> prueban la causa. Plan B: paso 8 de `scripts/demo_respaldo.py`.

### 1. El problema (0:20)
**Decir:** «Un grupo con seis empresas, tres monedas y seis formatos de archivo distintos consolida hoy a mano:
semanas de trabajo, ventas entre empresas contadas dos veces y errores que nadie ve hasta que ya contaminaron el
número del grupo. NEXUS lo consolida en segundos, sin captura manual, y cada cifra se puede rastrear hasta su
registro. Los datos de hoy son sintéticos.»

### 2. Seis formatos, cada uno contra su perfil (0:40)
**Mostrar:** pestaña *Perfiles e integridad*. Seis filas: XLSX, CSV, JSON; todas «Coincide con el perfil»; versión
v1; «Aprobado por: Santiago Enriquez Salguero». Bajar a la tabla de integridad.
**Decir:** «NEXUS corre dentro del servidor de la empresa: lee una carpeta en solo lectura, sin que nadie suba
archivos y sin internet. Cada archivo queda registrado con su SHA-256 y la app lo vuelve a calcular: todos
coinciden. Cada empresa tiene un perfil aprobado que dice cómo leer su formato; si un archivo deja de
coincidir con su perfil, la carga queda en revisión y no se procesa en silencio.»
**Cifras:** 6 de 6 cargas coinciden; 17 archivos con hash estable.

### 3. Un error sembrado, bloqueado (0:50)
**Mostrar:** el encabezado de 2026-10 (etiqueta **PROVISIONAL**) y la pestaña *Alertas y errores*, tabla de
registros fuera del consolidado y tabla de impacto.
**Decir:** «Esta depreciación de Transportes Ferrex México llegó con signo negativo: −240,000 pesos mexicanos, −12,000 dólares.
NEXUS no la corrige ni la ignora: la bloquea y la deja fuera del consolidado, con su importe y su motivo. Como no
sabemos cuál es el dato correcto, mostramos el rango: excluida, la utilidad es 359,125; si entrara tal como viene,
sube 12,000; con el signo corregido, baja 12,000. Por eso el período se marca **PROVISIONAL**: rango de utilidad
342,325 a 375,925 dólares. Ninguna cifra se modificó.»
**Opcional (10 s):** en 2026-11 hay una moneda «Q» que no es un código válido: se bloquea, no se adivina.
**Cifras:** EMP005 fila 7; 0 / +12,000 / −12,000; rango 342,325 – 375,925. (También hay una cuenta sin mapear
de 4,800 USD y un duplicado de factura excluido con ajuste reversible; mencionarlos solo si preguntan.)

### 4. Consolidado de octubre (0:40)
**Mostrar:** pestaña *Estados financieros*, estado de resultados con las tres columnas.
**Decir:** «Sumar las seis empresas sin más da ingresos de 2,078,000 dólares. Pero las empresas se venden entre
sí: 93,000 dólares se contarían dos veces. NEXUS elimina solo lo que concilia exacto y el consolidado real es
**1,985,000**. La utilidad neta es **359,125** y no cambia, porque lo que sale de ingresos también sale de costos.
El balance cuadra.»
**Cifras:** ingresos 1,985,000 (ingenua 2,078,000); utilidad neta 359,125; 8 eliminaciones conciliadas.

### 5. La discrepancia que no se elimina (0:30)
**Mostrar:** período 2026-11, tabla de intercompañía.
**Decir:** «Distribuidora Central dice haber vendido 20,000 dólares a Ferrex México; México dice haber
comprado 18,000. NEXUS no elimina a ciegas: abre una discrepancia de **2,000 dólares** para revisión y marca
el período como provisional. Es una sola diferencia: afecta tanto la operación (la venta) como el saldo (cuenta por
cobrar y por pagar), y no se elimina ninguna de las dos.»
*(La interfaz y el script de respaldo muestran la discrepancia una sola vez, con una nota de que afecta la operación
y el saldo.)*
**Cifras:** 20,000 vs 18,000 = 2,000 USD, referencia DC-IC-2611-MX.

### 6. De una cifra a su registro: Ingresos por ventas (cuenta 4000) (0:30)
**Mostrar:** pestaña *Trazabilidad*, elegir «Ingresos por ventas (cuenta 4000)».
**Decir:** «Elijo una cifra y veo de dónde sale: archivo, hoja y fila, el importe original, la moneda, la tasa del
mes y los dólares. Aquí, Ferrex México, hoja “Presupuesto MX”, fila 5: 7,200,000 pesos mexicanos por 0.05 son
360,000 dólares. Y abajo, los ajustes: cada eliminación intercompañía con su regla y su motivo.»
**Aclarar (una frase):** «Esta cifra es solo la cuenta 4000, ingresos por ventas. El total de ingresos del
consolidado, 1,985,000 dólares, incluye otras cuentas de ingresos, como los ingresos por servicios (cuenta 4100) de
Transportes Ferrex México, 120,000 dólares.»
**Cifras:** cuenta 4000: 1,948,000 antes de eliminar, 1,865,000 después (11 registros, 4 ajustes).

### 7. Indicadores (0:40)
**Mostrar:** pestaña de indicadores (o paso 7 del script de respaldo).
**Decir:** «ROIC, ROCE y EVA salen de las cifras consolidadas, con la fórmula y las entradas a la vista. Son
**mensuales**. El WACC de 8%, la tasa de impuesto de 25% y la definición de capital son **supuestos nuestros**,
marcados como tales, no datos del reto; además el validador bloquea un WACC escrito como 8 en vez de 0.08. Con
datos sintéticos, octubre da ROIC de 11.16% del mes, ROCE de 13.00% y EVA de 305,553 dólares del mes.»
**Cifras:** NOPAT 324,975; capital invertido 2,913,250; ROIC 11.16%; ROCE 13.00%; EVA 305,553.33 (mensual).
*Nota al pie (solo si preguntan):* la interfaz y el script también pueden mostrar cifras anualizadas, pero **no
son representativas por ser datos sintéticos**; no se presentan en la demo.

### 8. Una variación explicada (0:30)
**Mostrar:** período **2026-11**, pestaña *Variaciones*: la frase de la utilidad neta y su tabla de causas.
**Decir:** «La utilidad neta baja 80,315 dólares entre octubre y noviembre. No es un número suelto: el motor lo
descompone en causas que suman exacto. Operación, menos 55,815; ajustes y registros bloqueados, más 17,000; mes
faltante de una empresa (Ferrex Importaciones no entregó noviembre), menos 69,000. Y queda una parte **sin
explicar**, más 27,500 dólares: es la planilla de Distribuidora Central, que llegó con la moneda “Q”, bloqueada y sin
valor en dólares. NEXUS no adivina: lo dice. Todo es calculado con plantillas, sin IA, y cada línea se abre hasta
archivo, hoja y fila. Está marcado **PROVISIONAL** porque hay datos sin resolver.»
**Cifras:** −80,315 (−22.4%): operación −55,815; ajustes y bloqueados +17,000; mes faltante −69,000; sin explicar
+27,500 (EMP002, cuenta 6000, moneda «Q»).

### Cierre (0:20)
«Resumen: seis formatos, un consolidado en dólares, ninguna cifra sin origen, y todo lo dudoso queda visible y
marcado provisional en lugar de esconderse. Corre dentro del servidor, sin internet, y los datos de hoy son
sintéticos. Lo que sigue es la hoja de ruta.»

## Extras opcionales de la interfaz (si sobra tiempo)
- **Pestaña Hallazgos** (sección propia del menú horizontal): una ficha por hallazgo con *qué pasó, dónde (archivo, hoja, fila), por qué importa (USD y
  utilidad), causa probable y acción humana*, con contador por tipo y ordenada por impacto. Buen complemento del
  paso 3: abrir la ficha de la depreciación (signo invertido) y la de la moneda «Q» (*probable alias de GTQ, pero
  requiere aprobación humana; NEXUS no la convierte sola*).
- **Ficha de balance descuadrado**: lista causas candidatas en orden (registro igual al desbalance, importe × 2,
  duplicado, registros fuera de balance, diferencia de tasa) o «causa no identificada». **Con los datos sintéticos el
  balance cuadra, así que esta ficha no aparece en la demo**; se verifica en `tests/test_diagnostico.py`. Decirlo así
  si preguntan, y presentarlo como diagnóstico por coincidencias numéricas, no como certeza.
- **Nivel de confianza del período** (arriba): registros limpios vs. bloqueados o pendientes y por qué es PROVISIONAL.
- **Descargar paquete de auditoría**: zip con el consolidado, ajustes, alertas, discrepancias, perfiles y hashes SHA-256.
- **Simulador**: mueve la tasa de MXN o GTQ entre −10 % y +10 % y ve el efecto en el consolidado y los indicadores,
  con la etiqueta **SIMULACIÓN** (no modifica datos ni archivos).
- **Ayuda**: glosario, preguntas frecuentes y lo que NEXUS no puede detectar (contenido fijo).
- La matriz de errores y sus limitaciones están en `docs/VERIFICACION.md`.

## Versión corta (3 minutos)
Pasos 1 (0:15), 2 (0:30), 3 (0:40), 4 (0:35), 5 (0:20), 6 (0:30), cierre (0:10). Omitir 7 y 8.

## Hoja de ruta (lo que NO está construido)
Decirlo como plan, sin fechas ni promesas:
- **Clasificador local de anomalías**, sin nube: se entrenaría con ejemplos etiquetados generados con
  semillas distintas y se mediría con una semilla no usada al entrenar, comparado contra «solo reglas». **No existe
  todavía; no hay ningún modelo entrenado.**
- **Ingesta automática**: carpeta vigilada por empresa y modo lote para histórico; proponer el perfil de una empresa
  nueva. Hoy la carga se ejecuta a mano.
- **Conectores a sistemas contables** (ERP). Hoy solo se leen archivos XLSX, CSV y JSON.
- Prueba con **datos reales** de una empresa del grupo.

## Preguntas probables del jurado y respuestas honestas
| Pregunta | Respuesta |
|---|---|
| ¿Con qué datos entrenaron la IA? | No hay IA entrenada. El motor es determinista: reglas y cálculos reproducibles. Un clasificador local es parte de la hoja de ruta, pero no está construido ni medido; no queremos prometer una precisión que no tenemos. |
| ¿Esto funciona con datos reales? | No lo hemos probado con datos reales. Todo se probó con un grupo sintético con errores sembrados. La arquitectura está pensada para eso: cada empresa se incorpora con un perfil, sin tocar el motor, y lo probamos agregando una empresa nueva en las pruebas. |
| ¿Qué pasa si cambia el formato de un archivo? | La carga de esa empresa queda en revisión con el motivo (por ejemplo, «falta el encabezado X»), no se procesa en silencio con un mapeo incorrecto, y el período se marca provisional. Se corrige actualizando y aprobando el perfil. Hay pruebas de esto. |
| ¿Cómo saben que los números son correctos? | Contra una clave de respuestas calculada aparte, con Decimal, independiente del motor; 134 pruebas, entre ellas que el balance cuadre y que eliminar no cambie la utilidad. Es evidencia sobre datos sintéticos, no una auditoría. |
| ¿Por qué todos los períodos salen provisionales? | Porque hay datos sembrados sin resolver: registros bloqueados, una cuenta sin mapear, una discrepancia abierta o una empresa que no entregó un mes. Es intencional: preferimos marcar la duda que esconderla. |
| ¿De dónde salen las tasas de cambio? | De una tabla mensual del grupo, con una convención única (USD por unidad local, se multiplica). Son tasas sintéticas simples. Usamos la tasa del mes para resultados y balance, una simplificación; la norma contable usaría promedio y cierre. |
| ¿Qué tan confiables son ROIC, ROCE y EVA? | Las fórmulas son estándar y se calculan con las cifras consolidadas, pero WACC, impuesto y definición de capital son supuestos nuestros, visibles y editables. Son mensuales; no son una valoración. |
| ¿Cómo manejan los duplicados? | Mismo ID de factura: se excluye automáticamente con un ajuste registrado y reversible. Sin ID (mismo importe, fecha y contraparte): solo se marca, y una persona decide. |
| ¿Es seguro? ¿Dónde corre? | Dentro del servidor de la empresa, sin internet. Lee los archivos en solo lectura, registra su SHA-256 y no los modifica; hay pruebas que bloquean la red y verifican que los hashes no cambian. No tiene inicio de sesión ni control de accesos todavía. |
| ¿Qué hace NEXUS si el balance no cuadra? | Alerta y una ficha con causas **candidatas** en orden (un registro igual a la diferencia, un importe × 2 por signo invertido, un duplicado, registros fuera del balance o una diferencia de tasa) o «causa no identificada» con los registros más cercanos. Son coincidencias numéricas, no pruebas, y se calculan por empresa y período. Con los datos de la demo el balance cuadra; se probó con casos armados a mano. |
| ¿Y si una tasa de cambio se escribe mal? | Si cambia más de un umbral (15 %, configurable) frente al mes anterior se marca como sospechosa, con su impacto en USD, y se pide confirmación; no se bloquea ni se corrige. No se detecta la primera tasa de una moneda (sin historial) ni un cambio menor al umbral. |
| ¿Y si me reenvían el mismo archivo? | Dentro de una carga se advierte por hash idéntico o ID repetido. Entre ejecuciones, solo si se activa el historial (`--historial`); la interfaz no lo activa por defecto. Solo advierte: no excluye nada. |
| ¿Por qué no usaron un chatbot? | Porque un número que nadie puede auditar no sirve. Los cálculos son código determinista y ninguna IA calcula ni altera importes. Existe un **Asistente (prototipo)** opcional y apagado por defecto: es un modelo de lenguaje que solo explica resultados ya calculados, con la etiqueta visible y sin ver archivos ni filas crudas. Sin llave funciona en modo local con plantillas. |

## Qué NO decir
- «Usa IA» o «aprende de cada empresa»: no está construido.
- «Probado con datos reales» o «listo para producción».
- «Detecta todos los errores»: detecta los sembrados y las reglas definidas; lo no previsto puede pasar.
- Cifras de precisión o de tiempo ahorrado que no hayamos medido.
