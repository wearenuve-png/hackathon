# NEXUS — Motor de consolidación financiera multiempresa

Hackatón Open2 Build & Pitch, track Accounting. Brief completo en [CLAUDE.md](CLAUDE.md).

> Estado: motor (`nexus/`) con ingesta por perfiles y adaptadores, conversión, intercompañía, consolidación con
> trazabilidad y validador. 75 pruebas. Pantalla de avance en Streamlit.

## Cómo correrlo

```bash
.venv/bin/python -m pytest -q                              # pruebas (leen tests/fixtures/answer_key.json)
.venv/bin/python scripts/build_profiles.py --approved-by "Nombre"   # genera/versiona profiles/EMPxxx.json
.venv/bin/python scripts/run_pipeline.py --periodo 2026-10          # motor sin interfaz, exporta evidencia
.venv/bin/streamlit run app.py                                      # pantalla de avance
```

## Arquitectura multiempresa

Adaptadores (`nexus/adapters/`: Excel, CSV, JSON; `extract` + `normalize`) + perfiles por empresa
(`profiles/`) + modelo canónico (`nexus/schemas.py`). Lo particular de cada empresa vive en su perfil; si una
fuente no coincide con su perfil, la carga queda en REVISIÓN y no se procesa en silencio. Débito/crédito se
normaliza a un solo importe con el signo natural de la cuenta.

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
