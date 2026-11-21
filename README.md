# NEXUS — Motor de consolidación financiera multiempresa

Hackatón Open2 Build & Pitch, track Accounting. Brief completo en [CLAUDE.md](CLAUDE.md).

> Estado: motor (`nexus/`) con ingesta por perfiles y adaptadores, conversión, intercompañía, consolidación con
> trazabilidad y validador. 75 pruebas. Pantalla de avance en Streamlit.

## Para quien clona este repositorio

Requisito: Python 3.9 o superior y Git.

```bash
git clone https://github.com/wearenuve-png/hackathon.git
cd hackathon
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q
.venv/bin/streamlit run app.py
```

Las pruebas deben terminar en verde. La app se abre en `http://localhost:8501` y lee los archivos de
`data/synthetic/` (datos SINTÉTICOS) en solo lectura. `.venv/`, `__pycache__/` y `data/output/` no se versionan.

### Ramas y responsables

| Rama | Qué es | Archivos propios |
|---|---|---|
| `main` | Línea estable: solo entra lo que pasa todas las pruebas | — |
| `feat/ui` | Interfaz | `app.py` (su dueño es el único que lo edita) |
| `feat/explicador` | Explicador de variaciones con plantillas | `nexus/variance.py` |
| `feat/indicadores` | ROIC, ROCE y EVA | `nexus/metrics.py`, `nexus/ui/tab_indicadores.py` |
| `feat/completar` | Matriz de errores, explicador de variaciones, simulador, paquete de auditoría y ayuda | `docs/VERIFICACION.md`, `nexus/variance.py`, `nexus/simulator.py`, `nexus/ui/` |

Si una rama aún no existe, créala desde `main`: `git checkout -b feat/ui`.
`nexus/schemas.py` y `data/synthetic/generate.py` son compartidos: se editan **solo avisando al equipo**.
Regla de trabajo: cada persona toca solo sus archivos, en su rama, y no se cambian las firmas existentes.

## Escenario con errores (demostración)

`data/demo_errores/` es una copia de `data/synthetic` con **7 errores sembrados más** (monto en blanco, texto en un campo
numérico, duplicado con el mismo ID, archivo que declara USD siendo GTQ, signo invertido, asiento omitido que descuadra el
balance y tasa mal escrita). Su clave está en `data/demo_errores/ANSWER_KEY.md`. Se regenera con:

```bash
.venv/bin/python scripts/generate_demo_errores.py
```

En la app, el selector **Escenario** (arriba de la pantalla, siempre visible) alterna entre «Datos limpios» y «Datos con errores (demostración)»;
ambos se leen en solo lectura. En «Alertas y errores» cada hallazgo con corrección propuesta tiene **Aprobar corrección**,
**Rechazar** y **Deshacer**. Aprobar **no modifica ningún archivo**: la decisión (quién, cuándo, valor y motivo) queda en
`data/output/aprobaciones.jsonl` y el consolidado se recalcula en memoria.

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
| Monedas del grupo | GTQ, MXN, USD |
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
