# Datos de DEMO (SINTÉTICOS): Grupo Ferrex

Generados con `python scripts/generar_demo.py`. No son datos del reto ni de Grupo AG.

El grupo es el mismo de `data/synthetic/`, pero estos archivos parecen sacados de un ERP:
- **Detalle por documento**, no una fila por cuenta: facturas por cliente, órdenes de compra por proveedor,
  planilla por departamento y saldos por banco y por cliente. Son unas 1,200 filas en total.
- **Excel con formato:** filas de título, encabezados con color, filtros, fechas por documento, una hoja
  **Resumen** con fórmulas SUMIFS y una hoja de **Notas**.
- **Formatos distintos por empresa:** CSV con `;` y coma decimal, CSV en Windows-1252, JSON exportado de SAP,
  libro en inglés con dos hojas.
- **10 errores escondidos dentro del detalle**, como pasaría en un archivo real. Cada uno de 5 archivos trae 2;
  Ferrex Importaciones (JSON) llega **limpio**.

| Archivo | Empresa | Formato | Filas |
|---|---|---|---|
| `aceros_ferrex_gt.xlsx` | EMP001 Aceros Ferrex (GTQ) | Excel, hojas Presupuesto / Resumen / Notas | 278 |
| `distribuidora_central_gt.csv` | EMP002 Distribuidora Central (GTQ) | CSV `;`, coma decimal, UTF-8 | 246 |
| `ferrex_mexico.xlsx` | EMP003 Ferrex México (MXN) | Excel con títulos, hojas Presupuesto MX / Resumen | 197 |
| `ferrex_el_salvador.xlsx` | EMP004 Ferrex El Salvador (USD) | Excel en inglés, hojas Income Statement / Balance Sheet / Notes | 205 |
| `transportes_ferrex_mx.csv` | EMP005 Transportes Ferrex (MXN) | CSV `,`, Windows-1252, fecha dd/mm/aaaa | 145 |
| `ferrex_importaciones_pa.json` | EMP006 Ferrex Importaciones (USD) | JSON (moneda a nivel de archivo) | 108 |

## Cómo usarlos en la app

1. `streamlit run app.py`
2. En la barra lateral, en **"Carpeta del servidor con los archivos"**, cambia `...\data\synthetic` por `...\data\demo`
   (deja la carpeta de perfiles como está).
3. En la pestaña **Perfiles por empresa**, los 6 archivos aparecen como "Coincide con el perfil".

## Qué error trae cada archivo y qué hace NEXUS

| # | Archivo | Error escondido | Mes | Regla | Qué hace NEXUS |
|---|---|---|---|---|---|
| 1 | `aceros_ferrex_gt.xlsx` | La factura **FAC-A-00053** (Materiales San Lucas, 43,301.84 GTQ) se exportó dos veces | Nov | DUP-01 | **La corrige:** excluye la copia con un ajuste reversible. El original no se borra |
| 2 | `aceros_ferrex_gt.xlsx` | La fila de control "Total gastos de operacion" dice 398,000, pero las partidas suman 386,000 GTQ | Dic | TOT-01 | **La corrige:** rechaza el total y consolida con las partidas |
| 3 | `distribuidora_central_gt.csv` | El flete **FLT-00006** trae moneda **"Q"** en lugar de GTQ | Oct | MON-01 | Bloquea el registro y lo deja fuera del consolidado |
| 4 | `distribuidora_central_gt.csv` | La línea de planilla **PLA-00009** es de 855,640 GTQ: la planilla del mes suma 4.6 veces lo normal | Dic | ATI-01 | La marca para "revisar", sin cambiar la cifra |
| 5 | `ferrex_mexico.xlsx` | Aparece la cuenta **"Comisiones bancarias"** (38,750.40 MXN), que no existe en el catálogo | Nov | MAP-01 | La deja pendiente de mapeo, fuera del consolidado |
| 6 | `ferrex_mexico.xlsx` | La compra **TF-IC-2612** está registrada en 196,000 MXN y el vendedor dice 208,000 (630 USD de diferencia) | Dic | IC-01 | Abre la discrepancia y **no** la elimina |
| 7 | `ferrex_el_salvador.xlsx` | La línea de Payroll **PAY-00001** viene con signo negativo | Oct | SIGN-01 | Bloquea el registro y muestra el impacto en la utilidad |
| 8 | `ferrex_el_salvador.xlsx` | Rent **RENT-GT-1126** = 160,000 "USD": la paga la oficina de Guatemala, así que en realidad son quetzales | Nov | ATI-01 | Detecta un **posible error de moneda** y lo explica (160,000 × 0.125 = 20,000 USD) |
| 9 | `transportes_ferrex_mx.csv` | Dos cargos de 18,400 MXN al Taller Mecánico Ruiz, el 18/12, sin número de documento | Dic | DUP-02 | Lo marca como **posible** duplicado; los dos siguen dentro hasta que una persona lo confirme |
| 10 | `transportes_ferrex_mx.csv` | Los intereses **INT-00003** traen el importe **"2O954.48"** (letra O en lugar de cero) | Nov | ING-01 | Bloquea el registro: importe no numérico |

## Resultado esperado (verificado con el motor)

- 10 alertas, una por error y ninguna de más. Los 3 meses quedan **PROVISIONALES**.
- Activo − (Pasivo + Patrimonio) = **0.00** en los 3 meses.
- Utilidad neta consolidada: Oct **355,294.95**, Nov **172,407.72**, Dic **224,288.00** USD.

## Guion sugerido (2 minutos)

1. **Abrir un archivo en Excel:** son cientos de facturas en 6 formatos distintos. Encontrar a mano una "Q", una
   letra O o una factura repetida toma horas.
2. **Oct:** el flete con moneda "Q" y el Payroll negativo se bloquean. En "Impacto en utilidad" se ve cuánto
   movería la cifra.
3. **Nov:** la factura FAC-A-00053 se excluye sola con un ajuste reversible (se ve en Trazabilidad → Ingresos).
   El Rent de 160,000 "USD" resulta ser quetzales.
4. **Dic:** el total de control se rechaza, la diferencia intercompañía no se elimina y la planilla atípica
   queda en "revisar".
