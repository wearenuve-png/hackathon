# NEXUS: Brief para Claude Code

Motor de consolidación financiera multiempresa. Hackatón Open2 Build & Pitch, track Accounting (Grupo AG).


## 0. Cómo usar este documento (instrucciones para Claude Code)

Este documento es la base del proyecto. Léelo completo antes de hacer nada. Los archivos oficiales del reto (en data/input/) y las instrucciones oficiales PREVALECEN sobre este brief: si algo no coincide, avísanos y no asumas.

- Paso 1: lee este brief y todo lo que haya en data/input/ (los 6 presupuestos, tabla de tasas, catálogo, instrucciones).
- Paso 2: dime qué formatos encontraste y qué preguntas abiertas hay (sección 11).
- Paso 3: entrégame un PLAN (esquema común, firmas de funciones, orden de construcción). No programes hasta que lo apruebe.
- Paso 4: construye módulo por módulo, cada uno con su prueba, en el orden de la sección 4.
- Si todavía no hay archivos del reto, genera un dataset sintético en data/synthetic/ con errores sembrados, claramente marcado como sintético, solo para desarrollar.

## 1. Qué es NEXUS

NEXUS es un motor de consolidación financiera multiempresa. Recibe los presupuestos de 6 empresas (formatos y monedas distintos) y entrega automáticamente un único resultado financiero del grupo en USD, sin captura manual, con cada cifra explicada y rastreable hasta el registro original.

La web (Streamlit) es solo la pantalla para cargar archivos, ver alertas y consultar resultados. El producto real es el motor que normaliza, valida, convierte, concilia, elimina y consolida.


## 2. Contexto del reto (Open2 Build & Pitch, track Accounting, Grupo AG)


### El problema

- Consolidación manual: cada empresa usa otro formato y los totales se suman a mano (semanas de trabajo).
- Ventas entre empresas del grupo: se cuentan doble.
- Varias monedas: cada país presupuesta en la suya, sin tasa oficial común.
- Rentabilidad a mano: ROIC, ROCE y EVA se copian a mano y un error pasa inadvertido.
- Desviación sin explicar: en la revisión nadie explica rápido por qué cambia una cifra.

### Lo que debe probar la demo

- Funciona con los datos que entrega el reto (grupo ficticio: 6 empresas, 3 monedas, errores sembrados a propósito).
- Encuentra los errores sembrados.
- Un director entiende el resultado sin ayuda, y cada cifra se rastrea hasta el registro que la originó.

### Lo que NO quieren

- Un chat que responde preguntas sobre un Excel, ni un dashboard bonito con un número que nadie pueda auditar.
- No se usan datos reales de Grupo AG: la demo corre con los datos entregados por el reto.

### Restricciones del equipo

- Máximo 6 horas para una demo funcional. Equipo de 4 personas. Prioridad: lo que funciona y se puede auditar.

## 3. Reglas no negociables

- Python es la autoridad de los cálculos. La IA (Claude API) nunca calcula ni altera importes: solo propone mapeos de encabezados/cuentas y redacta explicaciones a partir de resultados ya calculados.
- Dinero con decimal.Decimal, nunca float.
- Trazabilidad total: cada registro conserva empresa, archivo, hoja, fila, período, cuenta, importe original, moneda, tasa, importe USD, regla aplicada y ajustes. El dato original nunca se pierde.
- No adivinar: si una equivalencia de cuenta, moneda o contraparte es ambigua, el registro queda pendiente de confirmación.
- Intercompañía: solo se elimina lo conciliado. Si A registra 20,000 y la contraparte 18,000, se abre una discrepancia de 2,000 para revisión; no se elimina a ciegas.
- Duplicados: un duplicado confirmado (mismo ID de factura/transacción) se excluye mediante un ajuste registrado. Un posible duplicado (mismo importe, fecha y contraparte, sin ID) solo se marca, nunca se excluye solo.
- Una anomalía estadística significa 'revisar', no 'error'. No modifica cifras.
- Si falla la API de Claude, el flujo básico sigue funcionando con mapeos predefinidos y reglas locales.
- Reproducible: conservar los archivos originales y versionar las reglas para reproducir cualquier consolidado.

## 4. Qué vamos a armar (módulos y prioridad)


| Prioridad | Módulo | Criterio de aceptación |
|---|---|---|
| MUST | Ingesta y normalización | Los 6 presupuestos se leen y pasan al esquema común, con su origen (archivo, hoja, fila). |
| MUST | Conversión a USD | Se usa la tasa del mes; se conservan importe original, moneda, tasa y USD. |
| MUST | Eliminación intercompañía | Se emparejan y eliminan solo operaciones conciliadas; las diferencias quedan visibles. |
| MUST | Consolidación + trazabilidad | El resultado coincide con las pruebas y cada cifra se desglosa hasta su origen. |
| SHOULD (alta) | Validador | Detecta los errores sembrados, duplicados, totales inconsistentes, moneda faltante, cuentas sin mapear. |
| SHOULD | Explicador de variaciones | Compara períodos y explica solo lo que los datos respaldan. |
| SHOULD | Indicadores ROIC, ROCE, EVA | Se calculan con definiciones y datos confirmados; no se copian ni los genera la IA. |
| COULD | Interfaz ejecutiva / ML | Mejora la presentación o prioriza anomalías sin afectar el motor. |

Nota: el validador está marcado SHOULD (alta) porque el jurado busca los errores sembrados; se construye justo después de los 4 MUST.


## 5. Cómo lo vamos a hacer


### Flujo del motor


```
Archivos -> Ingesta -> Normalización -> Validación -> Conversión USD ->
Conciliación intercompañía -> Eliminaciones -> Consolidación ->
Indicadores y variaciones -> Reporte + auditoría
```

La trazabilidad atraviesa todas las etapas: cada resultado guarda origen, transformación, tasa, regla, ajuste y versión de ejecución.


### Estructura del proyecto


```
nexus/
  app.py                  # interfaz Streamlit
  data/input/             # archivos originales del reto
  data/synthetic/         # datos de desarrollo (solo si hace falta)
  data/normalized/  data/output/
  nexus/
    schemas.py            # contrato de datos (se crea PRIMERO)
    ingestion.py          # lectura XLSX/XLS/CSV (PDF/JSON si hay tiempo)
    mapping.py            # homologación de encabezados y cuentas
    validation.py         # reglas, duplicados, totales
    currency.py           # conversión a USD
    intercompany.py       # conciliación y eliminaciones
    consolidation.py      # consolidado
    metrics.py            # ROIC, ROCE, EVA
    variance.py           # comparación entre períodos
    audit.py              # trazabilidad y ajustes
    ai.py                 # Claude: mapeos propuestos y explicaciones
  tests/ (test_currency, test_duplicates, test_intercompany, test_consolidation)
  README.md
```


### Tecnologías


| Componente | Tecnología | Responsabilidad |
|---|---|---|
| Interfaz | Streamlit | Cargar archivos, ver alertas y resultados |
| Lectura | Pandas + OpenPyXL | Procesar Excel/CSV y normalizar |
| Reglas financieras | Python (Decimal) | Conversión, conciliación, eliminaciones, cálculos |
| IA | Claude API (claude-sonnet-5-5) | Proponer mapeos y redactar explicaciones |
| Persistencia | SQLite o archivos estructurados | Registros, ejecuciones, decisiones, auditoría |
| Salida | OpenPyXL | Exportar consolidado y evidencia |
| Anomalías (opcional) | scikit-learn (Isolation Forest) | Solo si hay datos suficientes y aporta algo demostrable |


### Esquema común mínimo (una fila normalizada)


```
{ "company_id": "EMP001", "period": "2026-01", "account_code": "4000",
  "account_name": "Ingresos", "amount_original": 150000, "currency": "GTQ",
  "counterparty_id": "EMP002", "transaction_id": "TX001",
  "source_file": "empresa_1.xlsx", "source_sheet": "Presupuesto", "source_row": 15 }
```

Después se agregan: tasa, orientación de la tasa, importe USD, estado de validación, id de conciliación y referencias de auditoría.


### Decisiones que NO se improvisan (documentar en README y probar)

- Orientación de la tasa: 'moneda local por 1 USD' (se DIVIDE) o 'USD por unidad local' (se MULTIPLICA). Definir una, y cubrir ambas con tests.
- Qué cuentas y movimientos se eliminan en la consolidación.
- Tolerancia de conciliación (parámetro configurable) y tratamiento de diferencias.
- Campos obligatorios para aceptar un registro.
- La moneda NO se infiere por el símbolo; se toma de un campo explícito o de la configuración de la empresa.

## 6. Hallazgos que debe detectar el motor


| Hallazgo | Método de detección | Acción del motor |
|---|---|---|
| Moneda desconocida | Campo vacío o código no reconocido | Bloquea el registro y pide confirmación |
| Total que no cuadra | Recalcula subtotales y total | Muestra la diferencia; no acepta el total inconsistente |
| Cuenta mal mapeada / sin mapear | Catálogo común y reglas | Pide mapeo o revisión |
| Venta duplicada | ID y comparación de atributos | Marca; excluye solo tras confirmación |
| Diferencia entre compañías | Conciliación de contraparte | Abre discrepancia; no elimina automáticamente |
| Importe atípico | Reglas y análisis estadístico/ML | Genera alerta; no modifica la cifra |


## 7. Ejemplos de control para las pruebas (calculados a mano)

Son ilustrativos. Cuando lleguen los datos reales del reto, reemplazarlos por los resultados esperados de esos datos.

- Conversión: 77,000 GTQ con tasa 7.7 GTQ por USD -> 77,000 / 7.7 = 10,000 USD (porque 7.7 x 10,000 = 77,000).
- Intercompañía: A vende a C por 30 USD. A: ingresos 100, costos 40, utilidad 60. C: ingresos 150, costos 90, utilidad 60. Suma: ingresos 250, costos 130, utilidad 120. Se eliminan 30 de ingresos (A) y 30 de costos (C): ingresos 220, costos 100, utilidad 120. La utilidad no cambia.
- Discrepancia: A registra 20,000 y la contraparte 18,000 -> 20,000 - 18,000 = 2,000 de discrepancia, sin eliminar.
- Duplicado: la factura FAC-001 aparece dos veces por 5,000 -> se marcan ambos registros; no basta con que dos ventas tengan el mismo importe.
- Variación: ventas de 100,000 a 130,000 -> +30,000 (+30%). Si un registro nuevo de 12,000 lo explica, se atribuyen 12,000; los 18,000 restantes quedan 'sin causa probada'.
- Moneda mal marcada: ventas 800 marcadas USD cuando el historial es 100 -> 800 / 100 = 8, que coincide con una tasa GTQ/USD de 8: alerta 'posible moneda local marcada como USD'.
- Indicadores (ejemplo): NOPAT 40,000 y capital invertido 400,000 -> ROIC = 40,000 / 400,000 = 10%. Con WACC 8%: EVA = 40,000 - (0.08 x 400,000) = 40,000 - 32,000 = 8,000.

## 8. Pruebas que deben pasar antes de la demo


| Prueba | Qué debe demostrarse |
|---|---|
| Moneda | Importe original, tasa y resultado USD son reproducibles |
| Duplicado | Uno evidente se marca; uno ambiguo no se elimina sin revisión |
| Intercompañía | Lo conciliado se elimina; las diferencias permanecen como alertas |
| Totales | Los totales recalculados coinciden con el resultado del motor |
| Variación | Cambio absoluto y % coincide con el cálculo manual |
| Trazabilidad | Una cifra del reporte llega a sus filas fuente y transformaciones |
| Formato | Se procesan los formatos reales presentes en los archivos del reto |


## 9. Demo (3 a 5 minutos) y contingencia


### Guion

- 1. Problema: 6 empresas, monedas y formatos distintos.
- 2. Entrada: cargar los archivos y mostrar cómo NEXUS los reconoce y normaliza.
- 3. Control: mostrar un error sembrado o duplicado y cómo se detecta.
- 4. Consolidación: conversión a USD y operaciones intercompañía conciliadas/eliminadas.
- 5. Explicación: comparar un período y explicar una variación con registros concretos.
- 6. Auditoría: elegir una cifra y abrir su origen, tasa, regla y ajustes.

### Contingencia

- Si falla la API de Claude: mapeos predefinidos y reglas locales.
- Si PDF/OCR consume mucho tiempo: priorizar Excel/CSV y documentar el alcance.
- Si el ML no aporta algo demostrable: quitarlo y usar reglas y análisis de variaciones.
- Si falla la interfaz: el motor debe ejecutarse desde un script y exportar el consolidado.

## 10. Equipo y cronograma (6 horas)


| Integrante | Responsabilidad | Entregable |
|---|---|---|
| 1 Data Engineer | Entrada y normalización | Función que lee archivos y devuelve registros normalizados con origen |
| 2 Financial Engineer | Conversión, conciliación, eliminaciones, consolidación | Motor determinista probado con datos de ejemplo |
| 3 AI Engineer | Claude, homologación asistida, explicador | Mapeos propuestos y explicaciones basadas en resultados |
| 4 Integración / Producto | Auditoría, interfaz, pruebas, demo | Flujo ejecutable de principio a fin |

Regla de coordinación: primero se crea schemas.py y los stubs con las firmas de cada función, para trabajar en paralelo. Cada módulo debe poder probarse por separado. La interfaz usa datos de prueba desde el inicio.


| Tiempo | Trabajo | Resultado |
|---|---|---|
| 00:00-00:30 | Revisar archivos, reglas, moneda base, catálogo y esquema común | Contrato de datos acordado |
| 00:30-02:00 | Construcción paralela de módulos | Ingesta, motor, IA e interfaz en progreso |
| 02:00-03:30 | Integrar y procesar las 6 empresas | Primer consolidado real |
| 03:30-04:30 | Probar conversiones, errores sembrados, duplicados, conciliación | Resultados verificados |
| 04:30-05:15 | Explicaciones, indicadores y reporte | Demo entendible para el jurado |
| 05:15-06:00 | Ensayar desde cero y preparar contingencia | Demo reproducible |


## 11. Preguntas abiertas (resolver en el Paso 2, con los archivos del reto)

- ¿Cuál es la moneda base (USD) y dónde está la tabla de tasas por mes? ¿Cómo está expresada la tasa (multiplicar o dividir)?
- ¿Existe catálogo de cuentas común? ¿Hay equivalencias por empresa?
- ¿Cómo se identifican las operaciones intercompañía (referencia, contraparte)?
- ¿Cuáles son los errores sembrados que se espera encontrar?
- ¿Qué períodos hay (para comparar contra el anterior) y qué formatos tiene cada archivo?
- ¿Cómo define el reto ROIC, ROCE y EVA, y hay datos suficientes para calcularlos?
- ¿Qué tolerancia de conciliación se acepta?
Mensaje del proyecto: NEXUS conecta presupuestos separados por empresa, formato y moneda, los transforma en una sola visión financiera del grupo, detecta inconsistencias y explica los resultados con evidencia. La IA ayuda a entender los datos; el motor financiero garantiza que los cálculos sean reproducibles.


## 12. Resoluciones del equipo (21 nov 2026) — prevalecen sobre los supuestos por defecto

- Tasa: columna `usd_por_unidad_local`, se MULTIPLICA (importe_usd = importe_local x tasa). Control: 80,000 GTQ x 0.125 = 10,000 USD. Existe una función explícita para el caso inverso, con prueba.
- Monedas del grupo: GTQ, MXN (peso mexicano) y USD. (Cambio de requisito posterior: los importes en USD del dataset sintético se conservaron idénticos.)
- Duplicados: mismo ID de transacción = confirmado, se excluye automáticamente mediante un ajuste registrado (motivo, regla, reversible; el registro original no se borra). Sin ID (mismo importe, fecha y contraparte) = posible duplicado: solo se marca, pendiente de confirmación humana.
- Resto de preguntas abiertas: se aplican los supuestos por defecto del plan.
- No hay datos oficiales: se trabaja con el grupo ficticio "Grupo Ferrex" en `data/synthetic/` (script `generate.py`, semilla fija). Clave de respuestas en `tests/fixtures/`.
- El motor es GENÉRICO: nada de nombres, filas o errores de este dataset dentro del código.
- `validador/` es un prototipo anterior, solo como referencia de ideas (usa float).
- Reglas de equipo: cada persona toca solo sus archivos, en su propia rama; todos prueban con el mismo dataset sintético.
