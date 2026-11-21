# Datos de DEMO (SINTÉTICOS): Grupo Ferrex

Generados con `python scripts/generar_demo.py`. No son datos del reto ni de Grupo AG.
Es el mismo grupo de `data/synthetic/`, pero con un juego de errores **nuevo** para la presentación:
5 archivos traen 2 errores cada uno y el de Ferrex Importaciones (JSON) llega **limpio**.

## Cómo usarlos en la app

1. `streamlit run app.py`
2. En la barra lateral, en **"Carpeta del servidor con los archivos"**, cambia `...\data\synthetic` por `...\data\demo`
   (deja la carpeta de perfiles como está).
3. Los 6 archivos se cargan como "Coincide con el perfil" (pestaña **Perfiles por empresa**).

## Qué error trae cada archivo y qué hace NEXUS

| # | Archivo | Error sembrado | Periodo | Regla | Qué hace NEXUS | Dónde se ve |
|---|---|---|---|---|---|---|
| 1 | `aceros_ferrex_gt.xlsx` (EMP001) | Factura **FAC-B-1120** (65,000 GTQ) registrada dos veces | Nov | DUP-01 | **Lo corrige:** excluye la copia con un ajuste registrado y reversible (-8,125 USD). El original no se borra | Alertas · Trazabilidad (Ingresos) |
| 2 | `aceros_ferrex_gt.xlsx` (EMP001) | "Total gastos de operacion" declarado 398,000 y las partidas suman 386,000 GTQ | Dic | TOT-01 | **Lo corrige:** rechaza el total y consolida con las partidas | Alertas |
| 3 | `distribuidora_central_gt.csv` (EMP002) | Moneda **"QTZ"** (no existe) en Transporte | Oct | MON-01 | Bloquea el registro; queda fuera del consolidado y el mes se marca PROVISIONAL | Alertas · Registros fuera |
| 4 | `distribuidora_central_gt.csv` (EMP002) | Planilla de 980,000 GTQ, **4.6 veces** su nivel habitual | Dic | ATI-01 | Lo marca "revisar"; no cambia la cifra | Alertas |
| 5 | `ferrex_mexico.xlsx` (EMP003) | Cuenta **"Comisiones bancarias"** que no existe en el catálogo | Nov | MAP-01 | La deja pendiente de mapeo, fuera del consolidado | Alertas · Registros fuera |
| 6 | `ferrex_mexico.xlsx` (EMP003) | Compra intercompañía **TF-IC-2612**: 196,000 MXN contra 208,000 del vendedor (630 USD de diferencia) | Dic | IC-01 | Abre la discrepancia y **no** elimina la operación | Alertas · Intercompañía |
| 7 | `ferrex_el_salvador.xlsx` (EMP004) | Payroll con **signo negativo** | Oct | SIGN-01 | Bloquea el registro y muestra el impacto en la utilidad | Alertas · Impacto en utilidad |
| 8 | `ferrex_el_salvador.xlsx` (EMP004) | Rent de 160,000 marcado **USD**: en realidad son quetzales (160,000 × 0.125 = 20,000 USD) | Nov | ATI-01 | Detecta un **posible error de moneda** y propone GTQ; no corrige sin confirmación | Alertas (columna Impacto) |
| 9 | `transportes_ferrex_mx.csv` (EMP005) | Dos cargos de 18,400 MXN al Taller Mecánico Ruiz, el mismo día y sin documento | Dic | DUP-02 | Lo marca como **posible** duplicado; los dos siguen dentro hasta que una persona lo confirme | Alertas |
| 10 | `transportes_ferrex_mx.csv` (EMP005) | Intereses con importe **"7O000.00"** (letra O en lugar de cero) | Nov | ING-01 | Bloquea el registro: importe no numérico | Alertas · Registros fuera |
| — | `ferrex_importaciones_pa.json` (EMP006) | Ninguno | — | — | Entra limpio | Perfiles por empresa |

## Resultado esperado

- Los 3 meses quedan **PROVISIONALES**, porque hay registros fuera del consolidado o alertas pendientes.
- Activo − (Pasivo + Patrimonio) = **0.00** en los 3 meses.
- Utilidad neta consolidada: Oct **400,875.00**, Nov **182,475.00**, Dic **222,356.00** USD.

## Guion sugerido (2 minutos)

1. **Oct:** "QTZ" no es una moneda, así que el registro se bloquea. El Payroll negativo también se bloquea, y en
   "Impacto en utilidad" se ve cuánto movería la cifra.
2. **Nov:** la factura duplicada se excluye sola con un ajuste reversible (se ve en Trazabilidad → Ingresos).
   El Rent de 160,000 "USD" resulta ser quetzales.
3. **Dic:** el total que no cuadra se rechaza, la diferencia intercompañía no se elimina y la planilla atípica
   queda en "revisar".
