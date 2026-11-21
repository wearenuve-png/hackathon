# NEXUS — Motor de consolidación financiera multiempresa

Hackatón Open2 Build & Pitch, track Accounting. Brief completo en [CLAUDE.md](CLAUDE.md).

> Estado: dataset sintético y clave de respuestas listos. El motor (`nexus/`) aún no está programado.

## Convenciones (no se improvisan)

| Tema | Decisión |
|---|---|
| Moneda de presentación | USD |
| Monedas del grupo | GTQ, HNL, USD |
| Tasa | `usd_por_unidad_local`, se **multiplica**: `importe_usd = importe_local × tasa`. Ej.: 80,000 GTQ × 0.125 = 10,000 USD. Caso inverso (`local_por_usd`, se divide) en una función explícita y probada. |
| Tasa usada | La del mes del registro, para resultados y balance (simplificación documentada; NIC 21 usaría promedio y cierre). |
| Dinero | `decimal.Decimal` siempre. Sin redondeo interno; se presenta a 2 decimales `ROUND_HALF_UP`. |
| Moneda de un registro | Campo explícito del archivo o configuración de la empresa (`empresas.csv`). Nunca se infiere por el símbolo. |
| Intercompañía | Solo con contraparte identificable (alias en `empresas.csv`). Se empareja por vendedor, comprador, período y referencia. Tolerancia: USD 1.00 (configurable). Fuera de tolerancia: discrepancia abierta, no se elimina nada. |
| Qué se elimina | Ventas IC contra costo/gasto IC del comprador, y CxC IC contra CxP IC. |
| Duplicados | Mismo ID = confirmado: se excluye con un ajuste registrado y reversible (el original no se borra). Sin ID (mismo importe, fecha y contraparte) = posible: solo se marca. |
| Registro bloqueado | Moneda inválida o signo invertido: no entra al consolidado hasta corregirse. |
| Cuenta sin mapear | Pendiente de confirmación; no entra al consolidado. |
| Anomalía | "Revisar", nunca modifica la cifra. |
| Filas de total | No se suman; se recalculan y se comparan. |
| Mes faltante | Se reporta y el consolidado del mes queda marcado como incompleto. |

## Datos

- `data/synthetic/` — **Grupo Ferrex, SINTÉTICO**. Regenerar: `.venv/bin/python data/synthetic/generate.py`
- `tests/fixtures/answer_key.json` y `ANSWER_KEY.md` — clave de respuestas calculada con Decimal, independiente del motor.
- `data/input/` — para archivos oficiales, si llegan. Prevalecen sobre el sintético.
