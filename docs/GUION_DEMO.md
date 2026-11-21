# Guion de demo NEXUS (3 a 5 minutos)

**Datos SINTÉTICOS** (Grupo Ferrex, generados con `data/synthetic/generate.py`). Nunca presentarlos como datos reales.
Antes de empezar: `.venv/bin/streamlit run app.py`, período **2026-10** seleccionado. Plan B si falla la app o el
proyector: `.venv/bin/python scripts/demo_respaldo.py` (corre todo sin interfaz, en menos de un segundo, imprime
las mismas cifras y exporta la evidencia a `data/output/`).

## Recorrido (4:40 + 0:20 de cierre = 5:00)

| # | Tiempo | Paso | Dónde en la app |
|---|---|---|---|
| 1 | 0:00 – 0:20 | El problema | — |
| 2 | 0:20 – 1:00 | 6 formatos, perfiles y hashes | Pestaña **Perfiles por empresa** |
| 3 | 1:00 – 1:50 | Error bloqueado, rango de impacto, PROVISIONAL | Encabezado + pestaña **Alertas y exclusiones** |
| 4 | 1:50 – 2:30 | Consolidado de octubre vs. suma ingenua | Pestaña **Resultados y balance** |
| 5 | 2:30 – 3:00 | Discrepancia intercompañía | Período **2026-11**, **Alertas y exclusiones** |
| 6 | 3:00 – 3:30 | Clic hasta archivo, hoja y fila | Pestaña **Trazabilidad** |
| 7 | 3:30 – 4:10 | ROIC, ROCE y EVA | Pestaña de indicadores (ver nota) |
| 8 | 4:10 – 4:40 | Una variación explicada | **PENDIENTE** (ver nota) |
| — | 4:40 – 5:00 | Cierre y hoja de ruta | — |

> **Nota paso 7:** la pestaña existe como `nexus/ui/tab_indicadores.py` (`render(consolidado, periodo)`), pero
> **no está conectada en `app.py`** (su dueño debe agregarla). Mientras no lo esté, mostrar este paso con
> `scripts/demo_respaldo.py` (paso 7) y decirlo tal cual.
>
> **Nota paso 8:** `nexus/variance.py` es todavía un esqueleto. **Paso pendiente**: no se muestra en vivo. Si el
> explicador se integra antes de la demo, mostrar la comparación 2026-10 vs. 2026-11 con registros concretos;
> si no, pasarlo a la hoja de ruta (ver más abajo).

### 1. El problema (0:20)
**Decir:** «Un grupo con seis empresas, tres monedas y seis formatos de archivo distintos consolida hoy a mano:
semanas de trabajo, ventas entre empresas contadas dos veces y errores que nadie ve hasta que ya contaminaron el
número del grupo. NEXUS lo consolida en segundos, sin captura manual, y cada cifra se puede rastrear hasta su
registro. Los datos de hoy son sintéticos.»

### 2. Seis formatos, cada uno contra su perfil (0:40)
**Mostrar:** pestaña *Perfiles por empresa*. Seis filas: XLSX, CSV, JSON; todas «Coincide con el perfil»; versión
v1; «Aprobado por: Santiago Enriquez Salguero». Bajar a la tabla de integridad.
**Decir:** «NEXUS corre dentro del servidor de la empresa: lee una carpeta en solo lectura, sin que nadie suba
archivos y sin internet. Cada archivo queda registrado con su SHA-256 y la app lo vuelve a calcular: todos
coinciden. Cada empresa tiene un perfil aprobado que dice cómo leer su formato; si un archivo deja de
coincidir con su perfil, la carga queda en revisión y no se procesa en silencio.»
**Cifras:** 6 de 6 cargas coinciden; 17 archivos con hash estable.

### 3. Un error sembrado, bloqueado (0:50)
**Mostrar:** el encabezado de 2026-10 (etiqueta **PROVISIONAL**) y la pestaña *Alertas y exclusiones*, tabla de
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
**Mostrar:** pestaña *Resultados y balance*, estado de resultados con las tres columnas.
**Decir:** «Sumar las seis empresas sin más da ingresos de 2,078,000 dólares. Pero las empresas se venden entre
sí: 93,000 dólares se contarían dos veces. NEXUS elimina solo lo que concilia exacto y el consolidado real es
**1,985,000**. La utilidad neta es **359,125** y no cambia, porque lo que sale de ingresos también sale de costos.
El balance cuadra.»
**Cifras:** ingresos 1,985,000 (ingenua 2,078,000); utilidad neta 359,125; 8 eliminaciones conciliadas.

### 5. La discrepancia que no se elimina (0:30)
**Mostrar:** período 2026-11, tabla de intercompañía.
**Decir:** «Distribuidora Central dice haber vendido 20,000 dólares a Ferrex México; México dice haber
comprado 18,000. NEXUS no elimina a ciegas: abre una discrepancia de **2,000 dólares** para revisión y marca
el período como provisional. Aparecen dos filas porque la discrepancia afecta tanto la operación (la venta)
como el saldo (cuenta por cobrar y por pagar).»
**Cifras:** 20,000 vs 18,000 = 2,000 USD, referencia DC-IC-2611-HN.

### 6. De una cifra a su registro: Ingresos por ventas (cuenta 4000) (0:30)
**Mostrar:** pestaña *Trazabilidad*, elegir «4000 - Ingresos por ventas».
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

### 8. Una variación explicada (0:30) — PENDIENTE
No construido. Si no se integra, decir en este punto: «La comparación entre períodos con explicación basada en
registros concretos es lo siguiente en nuestra hoja de ruta.» No improvisar una explicación.

### Cierre (0:20)
«Resumen: seis formatos, un consolidado en dólares, ninguna cifra sin origen, y todo lo dudoso queda visible y
marcado provisional en lugar de esconderse. Corre dentro del servidor, sin internet, y los datos de hoy son
sintéticos. Lo que sigue es la hoja de ruta.»

## Versión corta (3 minutos)
Pasos 1 (0:15), 2 (0:30), 3 (0:40), 4 (0:35), 5 (0:20), 6 (0:30), cierre (0:10). Omitir 7 y 8.

## Hoja de ruta (lo que NO está construido)
Decirlo como plan, sin fechas ni promesas:
- **Explicador de variaciones** con plantillas a partir de los cálculos del motor (en desarrollo, no integrado).
- **Clasificador local de anomalías**, sin chatbot ni nube: se entrenaría con ejemplos etiquetados generados con
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
| ¿Por qué no usaron un chatbot? | Porque un número que nadie puede auditar no sirve. Los cálculos son código determinista; no hay IA que calcule ni altere importes. |

## Qué NO decir
- «Usa IA» o «aprende de cada empresa»: no está construido.
- «Probado con datos reales» o «listo para producción».
- «Detecta todos los errores»: detecta los sembrados y las reglas definidas; lo no previsto puede pasar.
- Cifras de precisión o de tiempo ahorrado que no hayamos medido.
