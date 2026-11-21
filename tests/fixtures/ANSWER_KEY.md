# ANSWER KEY - Grupo Ferrex (SINTETICO)

Generado por `data/synthetic/generate.py`. No editar a mano.

## Errores sembrados

| # | Tipo | Empresa | Archivo | Hoja | Fila | Periodo |
|---|---|---|---|---|---|---|
| 1 | moneda_invalida | EMP002 | distribuidora_central_gt.csv | - | 28 | 2026-11 |
| 2 | total_no_cuadra | EMP004 | ferrex_el_salvador.xlsx | Income Statement | 24 | 2026-11 |
| 3 | duplicado_confirmado | EMP001 | aceros_ferrex_gt.xlsx | Presupuesto | 3 | 2026-10 |
| 3 | duplicado_confirmado | EMP001 | aceros_ferrex_gt.xlsx | Presupuesto | 4 | 2026-10 |
| 4 | posible_duplicado | EMP005 | transportes_ferrex_mx.csv | - | 23 | 2026-11 |
| 4 | posible_duplicado | EMP005 | transportes_ferrex_mx.csv | - | 24 | 2026-11 |
| 5 | cuenta_sin_mapear | EMP003 | ferrex_mexico.xlsx | Presupuesto MX | 13 | 2026-10 |
| 6 | diferencia_intercompania | EMP002 | distribuidora_central_gt.csv | - | 35 | 2026-11 |
| 6 | diferencia_intercompania | EMP002 | distribuidora_central_gt.csv | - | 45 | 2026-11 |
| 6 | diferencia_intercompania | EMP003 | ferrex_mexico.xlsx | Presupuesto MX | 35 | 2026-11 |
| 6 | diferencia_intercompania | EMP003 | ferrex_mexico.xlsx | Presupuesto MX | 45 | 2026-11 |
| 7 | importe_atipico | EMP002 | distribuidora_central_gt.csv | - | 51 | 2026-12 |
| 8 | signo_invertido | EMP005 | transportes_ferrex_mx.csv | - | 7 | 2026-10 |
| 9 | mes_faltante | EMP006 | ferrex_importaciones_pa.json | - | - | 2026-11 |

## Eliminaciones esperadas (USD)

| Periodo | Ref | Tipo | Vendedor -> Comprador | Cuentas | USD |
|---|---|---|---|---|---|
| 2026-10 | AF-IC-2610 | operacion | EMP001 -> EMP002 | 4000 / 5000 | 50000.00 |
| 2026-10 | AF-IC-2610 | saldo | EMP001 -> EMP002 | 1100 / 2000 | 50000.00 |
| 2026-10 | DC-IC-2610-MX | operacion | EMP002 -> EMP003 | 4000 / 5000 | 15000.00 |
| 2026-10 | DC-IC-2610-MX | saldo | EMP002 -> EMP003 | 1100 / 2000 | 15000.00 |
| 2026-10 | DC-IC-2610-SV | operacion | EMP002 -> EMP004 | 4000 / 5000 | 10000.00 |
| 2026-10 | DC-IC-2610-SV | saldo | EMP002 -> EMP004 | 1100 / 2000 | 10000.00 |
| 2026-10 | TF-IC-2610 | operacion | EMP005 -> EMP003 | 4100 / 6200 | 10000.00 |
| 2026-10 | FI-IC-2610 | operacion | EMP006 -> EMP003 | 4000 / 5000 | 8000.00 |
| 2026-11 | AF-IC-2611 | operacion | EMP001 -> EMP002 | 4000 / 5000 | 55000.00 |
| 2026-11 | AF-IC-2611 | saldo | EMP001 -> EMP002 | 1100 / 2000 | 55000.00 |
| 2026-11 | TF-IC-2611 | operacion | EMP005 -> EMP003 | 4100 / 6200 | 10000.00 |
| 2026-12 | AF-IC-2612 | operacion | EMP001 -> EMP002 | 4000 / 5000 | 54600.00 |
| 2026-12 | AF-IC-2612 | saldo | EMP001 -> EMP002 | 1100 / 2000 | 54600.00 |
| 2026-12 | TF-IC-2612 | operacion | EMP005 -> EMP003 | 4100 / 6200 | 10920.00 |

## Discrepancias (no se eliminan)

- 2026-11 DC-IC-2611-MX (operacion): EMP002 20000.00 vs EMP003 18000.00 -> diferencia 2000.00 USD
- 2026-11 DC-IC-2611-MX (saldo): EMP002 20000.00 vs EMP003 18000.00 -> diferencia 2000.00 USD

## Consolidado esperado (USD)

| Concepto | 2026-10 | 2026-11 | 2026-12 |
|---|---|---|---|
| ingresos | 1985000.00 | 1529340.00 | 2068746.00 |
| costo_ventas | 1143750.00 | 865740.00 | 1226094.00 |
| gastos_operativos | 407950.00 | 328180.00 | 526050.00 |
| ebit | 433300.00 | 335420.00 | 316602.00 |
| gastos_financieros | 19425.00 | 15545.00 | 20334.00 |
| impuestos | 54750.00 | 41065.00 | 56810.00 |
| utilidad_neta | 359125.00 | 278810.00 | 239458.00 |
| activo_total | 3973250.00 | 3263595.00 | 4262886.00 |
| pasivo_total | 1675750.00 | 1306435.00 | 1771300.00 |
| patrimonio | 2297500.00 | 1957160.00 | 2491586.00 |
| activo_menos_pasivo_y_patrimonio | 0.00 | 0.00 | 0.00 |

| Suma ingenua (sin eliminar) | 2026-10 | 2026-11 | 2026-12 |
|---|---|---|---|
| ingresos | 2078000.00 | 1594340.00 | 2134266.00 |
| costo_ventas | 1226750.00 | 920740.00 | 1280694.00 |
| utilidad_neta | 359125.00 | 278810.00 | 239458.00 |
