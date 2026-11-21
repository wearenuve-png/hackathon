# FinaCore — Motor de consolidación financiera multiempresa

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

## Datos de prueba (solo para desarrollo)

La pantalla **no trae datos precargados**: arranca en blanco y solo muestra lo que se carga con «Cargar presupuestos».
Las carpetas `data/synthetic/` y `data/demo_errores/` quedan en el repositorio únicamente como **material de pruebas
automáticas** (con sus claves de respuestas); la app no las abre por su cuenta. Para una demostración usa la carpeta
`data/demo/` (12 archivos de Mateo, con su `LEEME_DEMO.md`). `data/demo_errores/` se regenera con
`.venv/bin/python scripts/generate_demo_errores.py`.

## Correrlo en cualquier computadora

1. Instala **Python 3.9 o superior** y **Git** (o descarga el repositorio como zip desde GitHub).
2. `git clone https://github.com/wearenuve-png/hackathon.git` y entra a la carpeta.
3. Abre la app con un solo comando (la primera vez instala las dependencias; necesita internet):
   - **Mac / Linux:** `./iniciar.sh`  (si no deja ejecutarlo: `bash iniciar.sh`)
   - **Windows:** doble clic en `iniciar.bat`
4. Se abre `http://localhost:8501` (si no, pégalo en el navegador). Otro puerto: `PUERTO=8502 ./iniciar.sh`.
5. Pulsa **Cargar presupuestos**, escribe la ruta de una carpeta y pulsa **Leer presupuestos**. Carpetas listas:
   `data/demo/` (6 empresas con 10 errores sembrados) y `data/demo_ampliado/` (12 empresas, 11 monedas, 2025-2027, limpias).

La app lee carpetas **de la computadora donde corre**: no se sube nada a internet y no necesita red (salvo el Asistente
conectado, que es opcional). El selector «Elegir carpeta…» solo existe en macOS; en Windows/Linux se escribe la ruta.

## Probar la web solo con GitHub (sin instalar nada)

**Opción A · GitHub Codespaces** (la más directa; solo hace falta una cuenta de GitHub con acceso al repositorio):
en la página del repositorio → **Code** → **Codespaces** → **Create codespace on feat/integracion**. Se instala solo y
la app se abre en el navegador (pestaña *Ports*, puerto 8501). Configuración en `.devcontainer/devcontainer.json`.

**Opción B · Streamlit Community Cloud** (un enlace público para compartir): en https://share.streamlit.io inicia sesión
con GitHub → **New app** → repositorio `wearenuve-png/hackathon`, rama `feat/integracion` (o `main` cuando se
fusione), archivo `app.py` → **Deploy**. Si el repositorio es privado, la app solo la verán las personas invitadas,
salvo que la publiques. Usa solo datos sintéticos.

En ambos casos la app corre en un servidor: no ve las carpetas de tu computadora. En «Cargar presupuestos» puedes
**subir los archivos** (presupuestos y las 5 tablas de configuración, todos juntos) o escribir la ruta de una carpeta del
repositorio: `data/demo` o `data/demo_ampliado`. El selector «Elegir carpeta…» solo existe en macOS local.

## Compartir con un enlace (Cloudflare Tunnel)

`./publicar.sh` arranca la app en **modo público** (`FINACORE_PUBLICO=1`) y abre un túnel de Cloudflare con un enlace
`https://….trycloudflare.com`; el enlace funciona mientras el script siga abierto. Requiere `cloudflared`
(`brew install cloudflared`). En modo público la app **no** acepta carpetas arbitrarias de la computadora: solo las del
proyecto (`data/demo`, `data/demo_ampliado`) o archivos subidos desde el navegador. Úsalo solo con datos sintéticos.

## Cargar tus propios presupuestos y Restablecer

- **Cargar presupuestos** (arriba, junto a Restablecer): escribe o elige una o varias carpetas (una por línea; en macOS
  hay un selector de carpeta). FinaCore lee los archivos XLSX, CSV y JSON **en solo lectura** y llena toda la pantalla con
  ellos. Deben estar los presupuestos y la configuración del grupo (`empresas.csv`, `tasas.csv`, `catalogo_cuentas.csv`,
  `equivalencias.csv`, `periodos.csv`); si falta algo, FinaCore dice qué y no adivina. Con varias carpetas trabaja sobre
  copias en `data/output/carga_auto/`; los originales no se tocan. Ejemplo: `data/demo/` (de Mateo).
- **Restablecer**: deja el programa **en blanco**: borra lo que guardó (decisiones aprobadas, manifiestos de huellas,
  copias de trabajo, carga elegida y estado de la pantalla) y no muestra ninguna cifra, gráfica ni tabla hasta que
  cargues una carpeta con «Cargar presupuestos». **No** borra tus presupuestos, los archivos de prueba del repositorio
  ni evidencias exportadas.

## Asistente FinaCore (prototipo, opcional)

Pestaña **Asistente**: un modelo de lenguaje que explica resultados **ya calculados** de la pantalla (no calcula, no corrige,
no aprueba). Está **apagado por defecto**: sin `ANTHROPIC_API_KEY` funciona en *modo local* con 6 preguntas sugeridas
respondidas con plantillas, sin red. Para el modo conectado:

```bash
.venv/bin/pip install -r requirements-asistente.txt
export ANTHROPIC_API_KEY=...        # solo en tu entorno; nunca en el repositorio (.env está en .gitignore)
```

El modelo se cambia en `config/asistente.json` (por defecto `claude-haiku-5-5`). Solo recibe un resumen calculado del
escenario y período actuales (cifras, fichas, variaciones, confianza, huellas de archivos), nunca archivos ni filas
crudas. Código en `asistente/`, fuera de `nexus/` (el motor no importa librerías de red).

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
