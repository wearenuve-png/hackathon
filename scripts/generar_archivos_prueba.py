"""ARCHIVOS DE PRUEBA AMPLIADOS (SINTETICOS) - NO SON DATOS DEL RETO NI DE GRUPO AG.

Genera un grupo completo y autocontenido de 12 empresas en 11 monedas, 3 años (2025-01 a 2027-03), con presupuestos en
XLSX, CSV y JSON y su configuracion (empresas, tasas, catalogo, equivalencias, periodos). Sirve para probar «Cargar
presupuestos» con mas archivos que el demo de 6. Los archivos salen LIMPIOS (sin errores sembrados): sirven para ver
el consolidado multianio; los errores los trae el demo de data/demo/.

    python scripts/generar_archivos_prueba.py [carpeta_salida]

Semilla fija: la salida es identica en cada ejecucion. No toca ningun otro dato del repositorio.
"""
import csv
import datetime as dt
import json
import random
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from openpyxl import Workbook

D = Decimal
C2 = D("0.01")
SEED = 20250101
PERIODOS = [f"{y}-{m:02d}" for y in (2025, 2026, 2027) for m in range(1, 13) if f"{y}-{m:02d}" <= "2027-03"]
ULTIMO_REAL = "2026-11"

# (id, nombre, pais, moneda, archivo, formato, ingreso mensual base en USD, tasa USD por unidad local inicial, estilo)
EMPRESAS = [
    ("EMP101", "Ferrex Honduras S.A.", "Honduras", "HNL", "ferrex_honduras.xlsx", "xlsx", 210_000, "0.0405", 0),
    ("EMP102", "Ferrex Colombia S.A.S.", "Colombia", "COP", "ferrex_colombia.csv", "csv", 340_000, "0.00025", 1),
    ("EMP103", "Ferrex Costa Rica S.A.", "Costa Rica", "CRC", "ferrex_costa_rica.json", "json", 180_000, "0.0019", 2),
    ("EMP104", "Ferrex Peru S.A.C.", "Peru", "PEN", "ferrex_peru.xlsx", "xlsx", 260_000, "0.27", 0),
    ("EMP105", "Ferrex Chile SpA", "Chile", "CLP", "ferrex_chile.csv", "csv", 300_000, "0.00105", 1),
    ("EMP106", "Ferrex Brasil Ltda.", "Brasil", "BRL", "ferrex_brasil.json", "json", 420_000, "0.18", 2),
    ("EMP107", "Ferrex Guatemala Norte S.A.", "Guatemala", "GTQ", "ferrex_guatemala_norte.xlsx", "xlsx", 190_000, "0.128", 1),
    ("EMP108", "Ferrex Mexico Sur S. de R.L.", "Mexico", "MXN", "ferrex_mexico_sur.csv", "csv", 380_000, "0.052", 0),
    ("EMP109", "Ferrex Panama Logistica S.A.", "Panama", "USD", "ferrex_panama_logistica.json", "json", 150_000, "1", 2),
    ("EMP110", "Ferrex Ecuador S.A.", "Ecuador", "USD", "ferrex_ecuador.xlsx", "xlsx", 170_000, "1", 2),
    ("EMP111", "Ferrex Nicaragua S.A.", "Nicaragua", "NIO", "ferrex_nicaragua.csv", "csv", 120_000, "0.027", 0),
    ("EMP112", "Ferrex Rep. Dominicana S.R.L.", "Rep. Dominicana", "DOP", "ferrex_rep_dominicana.json", "json", 230_000, "0.0170", 1),
]
# codigo -> nombre local por estilo (cada empresa nombra sus cuentas distinto: la equivalencia las une)
NOMBRES = {
    0: {"4000": "Ventas", "5000": "Costo de ventas", "6000": "Sueldos y salarios", "6100": "Alquileres",
        "6200": "Fletes", "6300": "Otros gastos", "6400": "Depreciacion", "7000": "Intereses", "8000": "Impuesto sobre la renta",
        "1000": "Caja y bancos", "1100": "Clientes", "1200": "Inventarios", "1500": "Activo fijo neto",
        "2000": "Proveedores", "2100": "Impuestos por pagar", "2500": "Prestamos", "3000": "Capital social",
        "3100": "Utilidades acumuladas"},
    1: {"4000": "Ingresos por ventas netas", "5000": "Costo de mercaderia vendida", "6000": "Gastos de personal",
        "6100": "Renta de locales", "6200": "Transporte y fletes", "6300": "Gastos generales", "6400": "Depreciaciones",
        "7000": "Gastos financieros", "8000": "ISR del periodo", "1000": "Efectivo", "1100": "Cuentas por cobrar",
        "1200": "Existencias", "1500": "Propiedad planta y equipo", "2000": "Cuentas por pagar",
        "2100": "Impuestos por pagar", "2500": "Deuda bancaria", "3000": "Capital", "3100": "Resultados acumulados"},
    2: {"4000": "Net revenue", "5000": "Cost of goods sold", "6000": "Payroll", "6100": "Rent", "6200": "Freight",
        "6300": "Other operating expenses", "6400": "Depreciation", "7000": "Interest expense", "8000": "Income tax",
        "1000": "Cash and banks", "1100": "Accounts receivable", "1200": "Inventory", "1500": "Fixed assets net",
        "2000": "Accounts payable", "2100": "Taxes payable", "2500": "Bank loans", "3000": "Share capital",
        "3100": "Retained earnings"},
}
ORDEN = ["4000", "5000", "6000", "6100", "6200", "6300", "6400", "7000", "8000",
         "1000", "1100", "1200", "1500", "2000", "2100", "2500", "3000", "3100"]
CATALOGO = [("1000", "Efectivo y equivalentes", "BG", "activo", "S", ""), ("1100", "Cuentas por cobrar", "BG", "activo", "S", ""),
            ("1200", "Inventario", "BG", "activo", "S", ""), ("1500", "Propiedad, planta y equipo neto", "BG", "activo", "N", ""),
            ("2000", "Cuentas por pagar", "BG", "pasivo", "S", ""), ("2100", "Impuestos por pagar", "BG", "pasivo", "S", ""),
            ("2500", "Prestamos bancarios", "BG", "pasivo", "N", ""), ("3000", "Capital social", "BG", "patrimonio", "N", ""),
            ("3100", "Utilidades retenidas", "BG", "patrimonio", "N", ""), ("4000", "Ingresos por ventas", "ER", "ingreso", "", ""),
            ("4100", "Ingresos por servicios", "ER", "ingreso", "", ""), ("5000", "Costo de ventas", "ER", "costo", "", ""),
            ("6000", "Gastos de personal", "ER", "gasto_operativo", "", ""), ("6100", "Alquileres", "ER", "gasto_operativo", "", ""),
            ("6200", "Fletes y transporte", "ER", "gasto_operativo", "", ""),
            ("6300", "Otros gastos operativos", "ER", "gasto_operativo", "", ""), ("6400", "Depreciacion", "ER", "gasto_operativo", "", ""),
            ("7000", "Gastos financieros", "ER", "gasto_financiero", "", ""), ("8000", "Impuesto sobre la renta", "ER", "impuesto", "", ""),
            ("TOT_ING", "Total ingresos", "ER", "total", "", "4000|4100"),
            ("TOT_GOP", "Total gastos de operacion", "ER", "total", "", "6000|6100|6200|6300|6400")]


def q(x) -> Decimal:
    return D(x).quantize(C2, rounding=ROUND_HALF_UP)


def tasas(rnd):
    """Tasa USD por unidad local por mes: caminata aleatoria suave (maximo ~0.8 % al mes)."""
    out = {}
    for _id, _n, _p, cur, _f, _fm, _b, r0, _s in EMPRESAS:
        if cur in {c for (_, c) in out}:
            continue
        r = D(r0)
        for p in PERIODOS:
            if cur != "USD":
                r = r * (D(1) + D(str(round(rnd.uniform(-0.008, 0.008), 5))))
            out[(p, cur)] = D(1) if cur == "USD" else r.quantize(D("0.0000001"))
    return out


def saldos(rnd, base_usd, tasa_por_mes):
    """{periodo: {codigo: importe en moneda local}}; balance exacto por construccion (3100 es el saldo que cuadra)."""
    out = {}
    for i, p in enumerate(PERIODOS):
        ing_usd = D(base_usd) * D(str(round((1.0 + 0.008 * i) * (1 + rnd.uniform(-0.04, 0.04)), 4)))
        t = tasa_por_mes[p]
        L = lambda usd: q(D(usd) / t)
        er = {"4000": L(ing_usd), "5000": L(ing_usd * D("0.62")), "6000": L(ing_usd * D("0.12")),
              "6100": L(ing_usd * D("0.03")), "6200": L(ing_usd * D("0.04")), "6300": L(ing_usd * D("0.03")),
              "6400": L(ing_usd * D("0.02")), "7000": L(ing_usd * D("0.01"))}
        antes = er["4000"] - sum(er[k] for k in ("5000", "6000", "6100", "6200", "6300", "6400", "7000"))
        er["8000"] = q(max(antes, D(0)) * D("0.25"))
        bg = {"1000": L(ing_usd * D("0.9")), "1100": L(ing_usd * D("1.4")), "1200": L(ing_usd * D("1.6")),
              "1500": L(ing_usd * D("3.0")), "2000": L(ing_usd * D("1.1")), "2100": L(ing_usd * D("0.2")),
              "2500": L(ing_usd * D("1.5")), "3000": L(ing_usd * D("2.0"))}
        activo = sum(bg[k] for k in ("1000", "1100", "1200", "1500"))
        bg["3100"] = activo - sum(bg[k] for k in ("2000", "2100", "2500", "3000"))
        out[p] = {**er, **bg}
    return out


def escribir(carpeta: Path, emp, datos):
    cid, nombre, _pais, cur, archivo, fmt, _b, _r, estilo = emp
    nom, ruta = NOMBRES[estilo], carpeta / archivo
    filas = [(p, nom[c], datos[p][c]) for p in PERIODOS for c in ORDEN]
    if fmt == "xlsx":
        wb = Workbook()
        ws = wb.active
        ws.title = "Presupuesto"
        ws.append(["Período", "Cuenta", "Descripción", "Monto", "Moneda", "Contraparte", "No. Factura"])
        for p, cuenta, imp in filas:
            ws.append([p, cuenta, None, float(imp), cur, None, None])
        wb.properties.created = wb.properties.modified = dt.datetime(2026, 11, 21, 12, 0, 0)   # misma salida siempre
        wb.save(ruta)
    elif fmt == "csv":
        with open(ruta, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["periodo", "cuenta", "importe", "moneda", "contraparte", "referencia"])
            for p, cuenta, imp in filas:
                y, m = p.split("-")
                w.writerow([f"{m}/{y}", cuenta, f"{imp:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), cur, "", ""])
    else:
        entradas = [{"period": f"{p}-01", "account": cuenta, "amount": float(imp), "counterparty": None,
                     "transaction_id": None} for p, cuenta, imp in filas]
        ruta.write_text(json.dumps({"company_name": nombre, "reporting_currency": cur, "source_system": "ERP - export",
                                    "entries": entradas}, ensure_ascii=False, indent=1), encoding="utf-8")


def main(salida: Path) -> None:
    salida.mkdir(parents=True, exist_ok=True)
    rnd = random.Random(SEED)
    tasa = tasas(rnd)
    for emp in EMPRESAS:
        propias = {p: tasa[(p, emp[3])] for p in PERIODOS}
        escribir(salida, emp, saldos(rnd, emp[6], propias))
    def tabla(nombre, cab, filas):
        with open(salida / nombre, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(cab)
            w.writerows(filas)
    tabla("empresas.csv", ["company_id", "nombre", "pais", "moneda_funcional", "actividad", "archivo", "alias"],
          [(e[0], e[1], e[2], e[3], "Comercializacion de ferreteria", e[4], e[1].replace(" S.A.", "").replace(" S.A.S.", "")) for e in EMPRESAS])
    tabla("tasas.csv", ["periodo", "moneda", "usd_por_unidad_local"],
          [(p, c, tasa[(p, c)]) for (p, c) in sorted(tasa)])
    tabla("catalogo_cuentas.csv", ["account_code", "account_name", "estado", "clase", "corriente", "total_de"], CATALOGO)
    tabla("equivalencias.csv", ["company_id", "cuenta_local", "account_code"],
          [(e[0], NOMBRES[e[8]][c], c) for e in EMPRESAS for c in ORDEN])
    tabla("periodos.csv", ["periodo", "tipo"], [(p, "real" if p <= ULTIMO_REAL else "presupuesto") for p in PERIODOS])


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/output/archivos_prueba_ampliados"))
