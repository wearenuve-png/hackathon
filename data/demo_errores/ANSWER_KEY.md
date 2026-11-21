# ANSWER KEY - data/demo_errores (SINTETICO)

Generado por `scripts/generate_demo_errores.py` (semilla 2027). No editar a mano.

Parte de una copia de `data/synthetic`, que **ya trae sus 9 errores base** (`tests/fixtures/ANSWER_KEY.md`) y no se modifica. Aqui se **agregan 7 errores**; la diferencia entre los dos escenarios son exactamente estos.

Acciones: **APLICADA_AUTOMATICAMENTE** = solo el duplicado exacto con el mismo ID (se excluye con un ajuste registrado y reversible). **PROPUESTA** = todo lo demas: el registro queda bloqueado o pendiente y NEXUS propone una correccion que una persona aprueba o rechaza; el archivo fuente nunca se modifica.

| # | Empresa | Archivo | Hoja | Fila | Que es | Regla | Accion | Valor leido | Valor propuesto |
|---|---|---|---|---|---|---|---|---|---|
| 1 | EMP003 | ferrex_mexico.xlsx | Presupuesto MX | 65 y 66 | Factura FAC-M-0902 dos veces (60,000 MXN = 3,000 USD). | DUP-01 | APLICADA_AUTOMATICAMENTE | 60000 / 60000 | - |
| 2 | EMP002 | distribuidora_central_gt.csv | - | 7 | Casilla de monto en blanco: «Gastos varios» de 2026-10 (era 40.000,00 GTQ). | ING-01 | PROPUESTA | (vacio) | 41000.00 |
| 3 | EMP005 | transportes_ferrex_mx.csv | - | 55 | Texto en un campo numerico: «1O,000» (letra O en vez de cero). | ING-01 | PROPUESTA | 1O,000 | 10000 |
| 4 | EMP001 | aceros_ferrex_gt.xlsx | Presupuesto | 2 a 66 (columna Moneda, 65 filas) | El archivo declara USD en todas sus filas, pero el perfil de la empresa dice GTQ. | CARGA-01 | PROPUESTA | USD | GTQ |
| 5 | EMP004 | ferrex_el_salvador.xlsx | Income Statement | 36 | Gasto de 4,000 USD con signo negativo (-4,000). | SIGN-01 | PROPUESTA | -4000 | 4000 |
| 6 | EMP006 | ferrex_importaciones_pa.json | entries | 36 | Falta el lado de activo de un asiento de 8,000 USD: solo esta «Trade payables» (pasivo +8,000). Activo - (pasivo + patrimonio) = -8,000 USD en 2026-12. | BAL-01 | PROPUESTA | 8000 | 8000 |
| 7 | GRUPO | tasas.csv | - | 9 | Tasa MXN de 2026-12 escrita 0.525 en vez de 0.0525 (decimal corrido: x10). | TAS-01 | PROPUESTA | 0.525 | 0.0525 |

## Que debe hacer NEXUS con cada uno

1. **DUP-01**: Se excluye la 2.a fila con un ajuste registrado y reversible.
2. **ING-01**: Usar la mediana del mismo rubro en los otros periodos (referencia, no certeza).
3. **ING-01**: Cambiar la letra O por el cero: 10,000 MXN.
4. **CARGA-01**: Procesar el archivo con la moneda del perfil (GTQ).
5. **SIGN-01**: Corregir el signo: +4,000 USD.
6. **BAL-01**: Agregar el asiento omitido por 8,000 USD en la cuenta de activo que elija una persona.
7. **TAS-01**: Corregir a 0.0525 (decimal corrido; queda a 5 % de la tasa del mes anterior).

## Efectos en cascada (consecuencias, no errores nuevos)

- **#4** deja la carga de EMP001 en revision: EMP001 no aporta registros y las operaciones intercompania con EMP002 quedan sin pareja hasta aprobar la correccion.
- **#7** multiplica por 10 todo lo valorado en MXN en 2026-12 y puede disparar tambien alertas de importe atipico de EMP003 y EMP005 en ese periodo; desaparecen al aprobar la tasa corregida.
- **#6** solo se ve en 2026-12 de EMP006 (balance); no cambia el estado de resultados.
