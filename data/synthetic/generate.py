"""DATOS SINTETICOS - NO SON DATOS DEL RETO NI DE GRUPO AG.

Genera el grupo ficticio "Grupo Ferrex" (ferreteria y materiales de construccion):
6 empresas, 3 monedas (GTQ, MXN, USD), 6 formatos distintos y 9 errores sembrados.

Uso (desde la raiz del repo):
    .venv/bin/python data/synthetic/generate.py

Salidas:
    data/synthetic/            archivos de las empresas + tablas del grupo
    tests/fixtures/answer_key.json  y  ANSWER_KEY.md   (clave de respuestas)

La clave se calcula aqui, con Decimal, a partir de la especificacion canonica de cada
linea; NO usa el motor de NEXUS. Es reproducible: semilla fija.
"""
import csv
import datetime as dt
import json
import random
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from openpyxl import Workbook

SEED = 2026
D = Decimal
HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
KEY_DIR = REPO / "tests" / "fixtures"

PERIODS = ["2026-10", "2026-11", "2026-12"]
PERIOD_TYPE = {"2026-10": "real", "2026-11": "real", "2026-12": "presupuesto"}

# Convencion acordada: usd_por_unidad_local, se MULTIPLICA (importe_usd = importe_local x tasa)
RATES = {
    ("2026-10", "GTQ"): D("0.125"), ("2026-11", "GTQ"): D("0.125"), ("2026-12", "GTQ"): D("0.130"),
    ("2026-10", "MXN"): D("0.05"), ("2026-11", "MXN"): D("0.05"), ("2026-12", "MXN"): D("0.0525"),
    ("2026-10", "USD"): D("1"), ("2026-11", "USD"): D("1"), ("2026-12", "USD"): D("1"),
}
IC_TOLERANCE_USD = D("1.00")

# Las cifras base de las empresas en MXN (BASE, IC_OPS y los importes sembrados) conservan las unidades de la
# version anterior del grupo; al generar se multiplican por esta escala. Como 0.05 / 0.04 = 0.0525 / 0.042 = 1/0.8,
# los importes en USD quedan IDENTICOS a los de esa version. Mismo orden de numeros aleatorios: misma semilla.
LOCAL_SCALE = {"MXN": D("0.8")}

COMPANIES = [
    dict(id="EMP001", name="Aceros Ferrex S.A.", country="Guatemala", currency="GTQ",
         activity="Planta: fabrica varilla y alambre", file="aceros_ferrex_gt.xlsx",
         fmt="XLSX, encabezados en espanol, una hoja", aliases=["Aceros Ferrex", "Aceros Ferrex S.A."]),
    dict(id="EMP002", name="Distribuidora Ferrex Central S.A.", country="Guatemala", currency="GTQ",
         activity="Distribuidora central regional", file="distribuidora_central_gt.csv",
         fmt="CSV con ';', coma decimal y punto de miles, UTF-8",
         aliases=["Distribuidora Ferrex Central", "Distribuidora Central GT", "Ferrex Distribution Center GT"]),
    dict(id="EMP003", name="Ferrex México S. de R.L. de C.V.", country="México", currency="MXN",
         activity="Tiendas minoristas México", file="ferrex_mexico.xlsx",
         fmt="XLSX con filas de titulo antes de la tabla", aliases=["Ferrex México", "Ferrex MX"]),
    dict(id="EMP004", name="Ferrex El Salvador S.A. de C.V.", country="El Salvador", currency="USD",
         activity="Tiendas minoristas El Salvador", file="ferrex_el_salvador.xlsx",
         fmt="XLSX en ingles, varias hojas (Income Statement, Balance Sheet, Notes)",
         aliases=["Ferrex El Salvador"]),
    dict(id="EMP005", name="Transportes Ferrex México S. de R.L. de C.V.", country="México", currency="MXN",
         activity="Logistica y transporte", file="transportes_ferrex_mx.csv",
         fmt="CSV con ',', punto decimal, codificacion Windows-1252, fecha dd/mm/aaaa",
         aliases=["Transportes Ferrex México", "Transportes Ferrex"]),
    dict(id="EMP006", name="Ferrex Importaciones S.A.", country="Panama", currency="USD",
         activity="Importacion de herramientas", file="ferrex_importaciones_pa.json",
         fmt="JSON, moneda a nivel de archivo (no por fila)", aliases=["Ferrex Importaciones"]),
]
CO = {c["id"]: c for c in COMPANIES}

# codigo, nombre, estado (ER/BG), clase, corriente (S/N, solo BG), total_de
CATALOG = [
    ("1000", "Efectivo y equivalentes", "BG", "activo", "S", ""),
    ("1100", "Cuentas por cobrar", "BG", "activo", "S", ""),
    ("1200", "Inventario", "BG", "activo", "S", ""),
    ("1500", "Propiedad, planta y equipo neto", "BG", "activo", "N", ""),
    ("2000", "Cuentas por pagar", "BG", "pasivo", "S", ""),
    ("2100", "Impuestos por pagar", "BG", "pasivo", "S", ""),
    ("2500", "Prestamos bancarios", "BG", "pasivo", "N", ""),
    ("3000", "Capital social", "BG", "patrimonio", "N", ""),
    ("3100", "Utilidades retenidas", "BG", "patrimonio", "N", ""),
    ("4000", "Ingresos por ventas", "ER", "ingreso", "", ""),
    ("4100", "Ingresos por servicios", "ER", "ingreso", "", ""),
    ("5000", "Costo de ventas", "ER", "costo", "", ""),
    ("6000", "Gastos de personal", "ER", "gasto_operativo", "", ""),
    ("6100", "Alquileres", "ER", "gasto_operativo", "", ""),
    ("6200", "Fletes y transporte", "ER", "gasto_operativo", "", ""),
    ("6300", "Otros gastos operativos", "ER", "gasto_operativo", "", ""),
    ("6400", "Depreciacion", "ER", "gasto_operativo", "", ""),
    ("7000", "Gastos financieros", "ER", "gasto_financiero", "", ""),
    ("8000", "Impuesto sobre la renta", "ER", "impuesto", "", ""),
    ("TOT_ING", "Total ingresos", "ER", "total", "", "4000|4100"),
    ("TOT_GOP", "Total gastos de operacion", "ER", "total", "", "6000|6100|6200|6300|6400"),
]

# Nombre local de cada cuenta por empresa -> codigo comun (equivalencias)
LOCAL = {
    "EMP001": {"4000": "Ventas de varilla y alambre", "5000": "Costo de produccion vendida",
               "6000": "Sueldos y salarios", "6100": "Alquiler de bodega", "6200": "Fletes",
               "6300": "Otros gastos", "6400": "Depreciacion de maquinaria", "7000": "Intereses bancarios",
               "8000": "ISR", "TOT_GOP": "Total gastos de operacion",
               "1000": "Caja y bancos", "1100": "Clientes", "1200": "Inventarios",
               "1500": "Maquinaria y equipo neto", "2000": "Proveedores", "2100": "Impuestos por pagar",
               "2500": "Prestamos bancarios", "3000": "Capital social", "3100": "Utilidades acumuladas"},
    "EMP002": {"4000": "Ventas netas", "5000": "Costo de mercaderia vendida", "6000": "Planilla",
               "6100": "Arrendamientos", "6200": "Transporte", "6300": "Gastos varios",
               "6400": "Depreciaciones", "7000": "Gastos financieros", "8000": "Impuesto sobre la renta",
               "1000": "Efectivo", "1100": "Cuentas por cobrar", "1200": "Inventario de mercaderia",
               "1500": "Mobiliario y equipo", "2000": "Cuentas por pagar", "2100": "ISR por pagar",
               "2500": "Deuda bancaria", "3000": "Capital pagado", "3100": "Resultados acumulados"},
    "EMP003": {"4000": "Ingresos netos", "5000": "Costo de ventas", "6000": "Salarios",
               "6100": "Alquileres de tiendas", "6200": "Servicios de transporte",
               "6300": "Otros gastos de operacion", "6400": "Depreciacion", "7000": "Intereses",
               "8000": "Impuesto sobre la renta",
               "1000": "Bancos", "1100": "Cuentas por cobrar clientes", "1200": "Inventario",
               "1500": "Activo fijo neto", "2000": "Proveedores", "2100": "Impuestos por pagar",
               "2500": "Prestamos", "3000": "Capital", "3100": "Utilidades retenidas"},
    "EMP004": {"4000a": "Store sales - hardware", "4000b": "Store sales - building materials",
               "TOT_ING": "Total revenue", "5000": "Cost of goods sold", "6000": "Payroll",
               "6100": "Rent", "6200": "Freight", "6300": "Other operating expenses",
               "6400": "Depreciation", "7000": "Interest expense", "8000": "Income tax",
               "1000": "Cash", "1100": "Accounts receivable", "1200": "Inventory", "1500": "PP&E, net",
               "2000": "Accounts payable", "2100": "Taxes payable", "2500": "Bank loans",
               "3000": "Share capital", "3100": "Retained earnings"},
    "EMP005": {"4100": "Ingresos por servicios de transporte", "6000": "Salarios de pilotos",
               "6100": "Alquiler de predio", "6300a": "Combustible y lubricantes",
               "6300b": "Mantenimiento de flota", "6400": "Depreciación de vehículos",
               "7000": "Intereses", "8000": "Impuesto sobre la renta",
               "1000": "Caja", "1100": "Cuentas por cobrar", "1500": "Vehículos neto",
               "2000": "Cuentas por pagar", "2100": "Impuestos por pagar", "2500": "Préstamo vehicular",
               "3000": "Capital", "3100": "Utilidades acumuladas"},
    "EMP006": {"4000": "Net revenue", "5000": "Cost of sales", "6000": "Salaries", "6100": "Office rent",
               "6300": "Other expenses", "6400": "Depreciation", "7000": "Interest", "8000": "Income tax",
               "1000": "Cash and equivalents", "1100": "Trade receivables", "1200": "Inventory",
               "1500": "Fixed assets", "2000": "Trade payables", "2100": "Tax payable",
               "2500": "Long-term debt", "3000": "Common stock", "3100": "Retained earnings"},
}
UNMAPPED_NAME = "Gastos de mercadeo y publicidad"   # error 5: NO esta en equivalencias

# Importes base de octubre en moneda local. "fijo" = no varia entre meses.
BASE = {
    "EMP001": {"4000": 1_800_000, "5000": 1_250_000, "6000": 180_000, "6100": ("fijo", 60_000),
               "6200": 45_000, "6300": 30_000, "6400": ("fijo", 70_000), "7000": 25_000, "8000": 50_000,
               "1000": 600_000, "1100": 900_000, "1200": 1_100_000, "1500": 4_500_000,
               "2000": 700_000, "2100": 60_000, "2500": 2_000_000, "3000": ("fijo", 3_000_000)},
    "EMP002": {"4000": 2_600_000, "5000": 1_500_000, "6000": 220_000, "6100": ("fijo", 96_000),
               "6200": 70_000, "6300": 40_000, "6400": ("fijo", 35_000), "7000": 20_000, "8000": 60_000,
               "1000": 450_000, "1100": 1_200_000, "1200": 1_800_000, "1500": 900_000,
               "2000": 800_000, "2100": 70_000, "2500": 600_000, "3000": ("fijo", 1_500_000)},
    "EMP003": {"4000": 9_000_000, "5000": 5_500_000, "6000": 900_000, "6100": ("fijo", 400_000),
               "6300": 150_000, "6400": ("fijo", 180_000), "7000": 90_000, "8000": 200_000,
               "1000": 1_500_000, "1100": 1_200_000, "1200": 6_000_000, "1500": 8_000_000,
               "2000": 2_500_000, "2100": 250_000, "2500": 4_000_000, "3000": ("fijo", 6_000_000)},
    "EMP004": {"4000a": 300_000, "4000b": 200_000, "5000": 280_000, "6000": 50_000, "6100": ("fijo", 20_000),
               "6200": 8_000, "6300": 6_000, "6400": ("fijo", 7_000), "7000": 3_000, "8000": 12_000,
               "1000": 80_000, "1100": 60_000, "1200": 250_000, "1500": 400_000,
               "2000": 90_000, "2100": 12_000, "2500": 200_000, "3000": ("fijo", 300_000)},
    "EMP005": {"4100": 3_000_000, "6000": 900_000, "6100": ("fijo", 150_000), "6300a": 600_000,
               "6300b": 250_000, "6400": ("fijo", 300_000), "7000": 80_000, "8000": 150_000,
               "1000": 700_000, "1100": 900_000, "1500": 5_000_000,
               "2000": 600_000, "2100": 150_000, "2500": 2_500_000, "3000": ("fijo", 2_000_000)},
    "EMP006": {"4000": 450_000, "5000": 300_000, "6000": 40_000, "6100": ("fijo", 15_000),
               "6300": 10_000, "6400": ("fijo", 5_000), "7000": 4_000, "8000": 15_000,
               "1000": 120_000, "1100": 150_000, "1200": 350_000, "1500": 200_000,
               "2000": 180_000, "2100": 15_000, "2500": 250_000, "3000": ("fijo", 200_000)},
}

# Operaciones intercompania: (periodo, ref, vendedor, comprador, importe vendedor, importe comprador,
#   cuenta vendedor, cuenta comprador, genera saldo CxC/CxP)
IC_OPS = [
    ("2026-10", "AF-IC-2610", "EMP001", "EMP002", 400_000, 400_000, "4000", "5000", True),
    ("2026-10", "DC-IC-2610-HN", "EMP002", "EMP003", 120_000, 375_000, "4000", "5000", True),
    ("2026-10", "DC-IC-2610-SV", "EMP002", "EMP004", 80_000, 10_000, "4000", "5000", True),
    ("2026-10", "TF-IC-2610", "EMP005", "EMP003", 250_000, 250_000, "4100", "6200", False),
    ("2026-10", "FI-IC-2610", "EMP006", "EMP003", 8_000, 200_000, "4000", "5000", False),
    ("2026-11", "AF-IC-2611", "EMP001", "EMP002", 440_000, 440_000, "4000", "5000", True),
    ("2026-11", "DC-IC-2611-HN", "EMP002", "EMP003", 160_000, 450_000, "4000", "5000", True),  # error 6
    ("2026-11", "TF-IC-2611", "EMP005", "EMP003", 250_000, 250_000, "4100", "6200", False),
    ("2026-12", "AF-IC-2612", "EMP001", "EMP002", 420_000, 420_000, "4000", "5000", True),
    ("2026-12", "TF-IC-2612", "EMP005", "EMP003", 260_000, 260_000, "4100", "6200", False),
]
# alias que cada empresa escribe para referirse a la otra
ALIAS_USED = {("EMP001", "EMP002"): "Distribuidora Ferrex Central", ("EMP002", "EMP001"): "Aceros Ferrex",
              ("EMP002", "EMP003"): "Ferrex MX", ("EMP003", "EMP002"): "Distribuidora Central GT",
              ("EMP002", "EMP004"): "Ferrex El Salvador", ("EMP004", "EMP002"): "Ferrex Distribution Center GT",
              ("EMP005", "EMP003"): "Ferrex México", ("EMP003", "EMP005"): "Transportes Ferrex",
              ("EMP006", "EMP003"): "Ferrex México", ("EMP003", "EMP006"): "Ferrex Importaciones"}

# Estados esperados de cada linea (lo que el motor DEBE hacer)
INCLUDED = {"ok", "possible_duplicate", "atypical", "ic_discrepancy"}
# ok                 entra al consolidado
# possible_duplicate entra, marcado, pendiente de revision humana
# atypical           entra, marcado "revisar" (una anomalia no modifica cifras)
# ic_discrepancy     entra, NO se elimina, discrepancia abierta
# excluded_duplicate excluido por ajuste registrado (mismo ID)
# pending_mapping    no entra hasta que se confirme el mapeo
# blocked            no entra (moneda invalida, signo invertido)
# total              fila de total: nunca entra, solo se verifica


def S(cid, x):
    """Importe base -> importe en la moneda local de la empresa (escala solo para MXN)."""
    v = D(x) * LOCAL_SCALE.get(CO[cid]["currency"], D(1))
    return int(v) if v == v.to_integral_value() else v


def line(cid, period, code, amount, **kw):
    loc_key = code
    code = code.rstrip("ab") if code[:-1].isdigit() or code.startswith("TOT") else code
    return dict(company_id=cid, period=period, code=code, local_account=LOCAL[cid].get(loc_key, kw.pop("local", None)),
                amount=D(amount), currency=kw.pop("currency", CO[cid]["currency"]),
                counterparty_text=kw.pop("cp_text", None), counterparty_id=kw.pop("cp_id", None),
                txn_id=kw.pop("txn", None), date=kw.pop("date", None), kind=kw.pop("kind", "normal"),
                statement="BG" if code[0] in "123" else "ER", status=kw.pop("status", "ok"),
                error=kw.pop("error", None), description=kw.pop("desc", ""))


def last_day(period):
    y, m = map(int, period.split("-"))
    nxt = dt.date(y + (m == 12), m % 12 + 1, 1)
    return nxt - dt.timedelta(days=1)


def build_lines(rnd):
    out = {cid: [] for cid in CO}
    for cid in CO:
        prev = {}
        for p in PERIODS:
            if cid == "EMP006" and p == "2026-11":
                continue                                                   # error 9: mes faltante
            amounts = {}
            for k, v in BASE[cid].items():
                if isinstance(v, tuple):
                    amounts[k] = S(cid, v[1])
                elif p == "2026-10":
                    amounts[k] = S(cid, v)
                else:
                    lo, hi = (0.95, 1.10) if p == "2026-11" else (0.97, 1.08)
                    amounts[k] = S(cid, int(round(v * rnd.uniform(lo, hi), -3)))
            prev = amounts
            ics_sell = [o for o in IC_OPS if o[0] == p and o[2] == cid]
            ics_buy = [o for o in IC_OPS if o[0] == p and o[3] == cid]
            L = out[cid]
            date = last_day(p)

            # ---------- estado de resultados
            for k in [k for k in amounts if k[0] in "45678"]:
                kw = {"date": date}
                if cid == "EMP002" and p == "2026-11" and k == "6000":
                    kw.update(currency="Q", status="blocked", error=1)                   # error 1
                if cid == "EMP002" and p == "2026-12" and k == "6100":
                    kw.update(currency="USD", status="atypical", error=7)                # error 7
                if cid == "EMP005" and p == "2026-10" and k == "6400":
                    L.append(line(cid, p, k, -amounts[k], status="blocked", error=8, **kw))  # error 8
                    continue
                L.append(line(cid, p, k, amounts[k], **kw))
                if cid == "EMP001" and p == "2026-10" and k == "4000":
                    for i in (1, 2):                                                     # error 3
                        L.append(line(cid, p, "4000", 40_000, cp_text="Constructora Maya", txn="FAC-A-0457",
                                      desc="Venta a Constructora Maya", date=date,
                                      status="ok" if i == 1 else "excluded_duplicate", error=3))
                if cid == "EMP005" and p == "2026-11" and k == "6300a":
                    for _ in (1, 2):                                                     # error 4
                        L.append(line(cid, p, "6300a", S(cid, "12500"), cp_text="Gasolinera del Norte",
                                      date=dt.date(2026, 11, 15), status="possible_duplicate", error=4))
            if cid == "EMP003" and p == "2026-10":
                L.append(line(cid, p, "UNMAPPED", S(cid, 120_000), local=UNMAPPED_NAME, status="pending_mapping",
                              error=5))                                                  # error 5
            for o in ics_sell:
                st, err = ("ic_discrepancy", 6) if o[1] == "DC-IC-2611-HN" else ("ok", None)
                L.append(line(cid, p, o[6], S(cid, o[4]), cp_text=ALIAS_USED[(cid, o[3])], cp_id=o[3], txn=o[1],
                              desc=f"Venta intercompania {o[1]}", date=date, status=st, error=err))
            for o in ics_buy:
                st, err = ("ic_discrepancy", 6) if o[1] == "DC-IC-2611-HN" else ("ok", None)
                L.append(line(cid, p, o[7], S(cid, o[5]), cp_text=ALIAS_USED[(cid, o[2])], cp_id=o[2], txn=o[1],
                              desc=f"Compra intercompania {o[1]}", date=date, status=st, error=err))
            # totales
            if cid == "EMP001":
                tot = sum(amounts[k] for k in ("6000", "6100", "6200", "6300", "6400"))
                L.append(line(cid, p, "TOT_GOP", tot, kind="total", status="total", date=date))
            if cid == "EMP004":
                tot = amounts["4000a"] + amounts["4000b"]
                err = None
                if p == "2026-11":
                    tot += 5_000                                                         # error 2
                    err = 2
                L.append(line(cid, p, "TOT_ING", tot, kind="total", status="total", error=err, date=date))

            # ---------- balance general (cuadra por construccion, en moneda local)
            bg = [line(cid, p, k, amounts[k], date=date) for k in ("1000", "1100", "1200", "1500", "2000",
                                                                   "2100", "2500", "3000") if k in amounts]
            for o in [o for o in ics_sell if o[8]]:
                st, err = ("ic_discrepancy", 6) if o[1] == "DC-IC-2611-HN" else ("ok", None)
                bg.append(line(cid, p, "1100", S(cid, o[4]), cp_text=ALIAS_USED[(cid, o[3])], cp_id=o[3], txn=o[1],
                               desc=f"Saldo por cobrar intercompania {o[1]}", date=date, status=st, error=err))
            for o in [o for o in ics_buy if o[8]]:
                st, err = ("ic_discrepancy", 6) if o[1] == "DC-IC-2611-HN" else ("ok", None)
                bg.append(line(cid, p, "2000", S(cid, o[5]), cp_text=ALIAS_USED[(cid, o[2])], cp_id=o[2], txn=o[1],
                               desc=f"Saldo por pagar intercompania {o[1]}", date=date, status=st, error=err))
            act = sum(x["amount"] for x in bg if x["code"][0] == "1")
            pas = sum(x["amount"] for x in bg if x["code"][0] in "23")
            bg.append(line(cid, p, "3100", act - pas, date=date))
            L.extend(bg)
    return out


# ---------------------------------------------------------------- escritura de archivos
def fmt_es(d):
    """400000 -> '400.000,00'"""
    s = f"{d:,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


MES_ES = {"10": "Oct", "11": "Nov", "12": "Dic"}


def write_emp001(lines, path):
    wb = Workbook()
    ws = wb.active
    ws.title = "Presupuesto"
    ws.append(["Período", "Cuenta", "Descripción", "Monto", "Moneda", "Contraparte", "No. Factura"])
    for x in lines:
        ws.append([x["period"], x["local_account"], x["description"], float(x["amount"]), x["currency"],
                   x["counterparty_text"], x["txn_id"]])
        x["source_sheet"], x["source_row"] = "Presupuesto", ws.max_row
    wb.save(path)


def write_emp002(lines, path):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["periodo", "cuenta", "importe", "moneda", "contraparte", "referencia"])
        for i, x in enumerate(lines, start=2):
            y, m = x["period"].split("-")
            w.writerow([f"{m}/{y}", x["local_account"], fmt_es(x["amount"]), x["currency"],
                        x["counterparty_text"] or "", x["txn_id"] or ""])
            x["source_sheet"], x["source_row"] = None, i


def write_emp003(lines, path):
    wb = Workbook()
    ws = wb.active
    ws.title = "Presupuesto MX"
    ws.append(["Ferrex México S. de R.L. de C.V."])
    ws.append(["Presupuesto y cifras reales - expresado en Pesos mexicanos (MXN)"])
    ws.append([])
    ws.append(["Mes", "Cuenta contable", "Valor", "Divisa", "Empresa relacionada", "Documento"])
    for x in lines:
        y, m = x["period"].split("-")
        ws.append([f"{MES_ES[m]} {y}", x["local_account"], float(x["amount"]), x["currency"],
                   x["counterparty_text"], x["txn_id"]])
        x["source_sheet"], x["source_row"] = ws.title, ws.max_row
    wb.save(path)


def write_emp004(lines, path):
    wb = Workbook()
    sheets = {"ER": wb.active, "BG": wb.create_sheet("Balance Sheet")}
    sheets["ER"].title = "Income Statement"
    for ws in sheets.values():
        ws.append(["Period", "Account", "Amount", "Currency", "Counterparty", "Invoice ID"])
    for x in lines:
        ws = sheets[x["statement"]]
        ws.append([dt.datetime.combine(last_day(x["period"]), dt.time()), x["local_account"],
                   float(x["amount"]), x["currency"], x["counterparty_text"], x["txn_id"]])
        x["source_sheet"], x["source_row"] = ws.title, ws.max_row
    notes = wb.create_sheet("Notes")
    notes.append(["Figures in US dollars. December 2026 is budget."])
    notes.append(["Prepared by: Finance SV"])
    wb.save(path)


def write_emp005(lines, path):
    with open(path, "w", encoding="cp1252", newline="") as f:
        w = csv.writer(f, delimiter=",")
        w.writerow(["fecha", "cuenta", "monto", "moneda", "cia_relacionada", "num_doc"])
        for i, x in enumerate(lines, start=2):
            w.writerow([x["date"].strftime("%d/%m/%Y"), x["local_account"], f"{x['amount']:.2f}",
                        x["currency"], x["counterparty_text"] or "", x["txn_id"] or ""])
            x["source_sheet"], x["source_row"] = None, i


def write_emp006(lines, path):
    entries = []
    for i, x in enumerate(lines, start=1):
        amt = x["amount"]
        entries.append({"period": x["period"], "account": x["local_account"],
                        "amount": int(amt) if amt == amt.to_integral_value() else float(amt),
                        "counterparty": x["counterparty_text"], "transaction_id": x["txn_id"]})
        x["source_sheet"], x["source_row"] = "entries", i
    doc = {"company_name": CO["EMP006"]["name"], "country": "Panama", "reporting_currency": "USD",
           "scenario_note": "2026-12 is budget", "entries": entries}
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")


WRITERS = {"EMP001": write_emp001, "EMP002": write_emp002, "EMP003": write_emp003,
           "EMP004": write_emp004, "EMP005": write_emp005, "EMP006": write_emp006}


def write_group_tables():
    with open(HERE / "empresas.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["company_id", "nombre", "pais", "moneda_funcional", "actividad", "archivo", "alias"])
        for c in COMPANIES:
            w.writerow([c["id"], c["name"], c["country"], c["currency"], c["activity"], c["file"],
                        "|".join(c["aliases"])])
    with open(HERE / "tasas.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["periodo", "moneda", "usd_por_unidad_local"])
        for (p, m), r in sorted(RATES.items()):
            w.writerow([p, m, str(r)])
    with open(HERE / "periodos.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["periodo", "tipo"])
        for p in PERIODS:
            w.writerow([p, PERIOD_TYPE[p]])
    with open(HERE / "catalogo_cuentas.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["account_code", "account_name", "estado", "clase", "corriente", "total_de"])
        w.writerows(CATALOG)
    with open(HERE / "equivalencias.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["company_id", "cuenta_local", "account_code"])
        for cid, m in LOCAL.items():
            for k, name in m.items():
                w.writerow([cid, name, k.rstrip("ab") if not k.startswith("TOT") else k])


# ---------------------------------------------------------------- clave de respuestas
def q2(d):
    return d.quantize(D("0.01"), rounding=ROUND_HALF_UP)


def usd(x):
    return x["amount"] * RATES[(x["period"], x["currency"])]


def build_answer_key(lines_by_co):
    all_lines = [x for ls in lines_by_co.values() for x in ls]
    for x in all_lines:
        x["file"] = CO[x["company_id"]]["file"]

    def loc(x):
        return {"company_id": x["company_id"], "file": x["file"], "sheet": x["source_sheet"],
                "row": x["source_row"], "period": x["period"], "account_local": x["local_account"],
                "amount_local": str(x["amount"]), "currency_written": x["currency"]}

    errors = {
        1: ("moneda_invalida", "Moneda 'Q' (simbolo, no codigo ISO). No se infiere: registro bloqueado, fuera del consolidado."),
        2: ("total_no_cuadra", "'Total revenue' != suma de sus partidas (diferencia 5,000 USD). El total no se acepta; se usan las partidas."),
        3: ("duplicado_confirmado", "Factura FAC-A-0457 dos veces (40,000 GTQ = 5,000 USD). Se excluye la segunda mediante ajuste registrado y reversible."),
        4: ("posible_duplicado", "Mismo importe, fecha y contraparte, sin ID. Solo se marca; ambos registros siguen en el consolidado."),
        5: ("cuenta_sin_mapear", "Cuenta local sin equivalencia en el catalogo. Queda pendiente de mapeo, fuera del consolidado."),
        6: ("diferencia_intercompania", "EMP002 registra 160,000 GTQ = 20,000 USD; EMP003 registra 360,000 MXN = 18,000 USD. Discrepancia 2,000 USD; no se elimina (venta y saldo)."),
        7: ("importe_atipico", "Arrendamientos 96,000 marcado USD; en oct y nov fue 96,000 GTQ = 12,000 USD. Razon 8 = 1/0.125: posible GTQ marcado como USD. Alerta 'revisar'; la cifra NO se modifica."),
        8: ("signo_invertido", "Depreciacion negativa (-240,000 MXN) en cuenta de gasto. Registro bloqueado hasta correccion."),
        9: ("mes_faltante", "EMP006 no trae 2026-11. El consolidado de 2026-11 queda marcado como incompleto."),
    }
    seeded = []
    for n, (kind, expl) in errors.items():
        rows = [loc(x) for x in all_lines if x["error"] == n]
        entry = {"id": n, "tipo": kind, "explicacion": expl, "ubicaciones": rows}
        if n == 9:
            entry["ubicaciones"] = [{"company_id": "EMP006", "file": CO["EMP006"]["file"], "period": "2026-11"}]
        seeded.append(entry)

    # eliminaciones intercompania esperadas
    elims, discrepancies = [], []
    for (p, ref, s, b, *_rest) in IC_OPS:
        for kind, sacct, bacct in (("operacion", None, None), ("saldo", "1100", "2000")):
            sl = [x for x in all_lines if x["txn_id"] == ref and x["company_id"] == s
                  and ((x["code"] == "1100") == (kind == "saldo"))]
            bl = [x for x in all_lines if x["txn_id"] == ref and x["company_id"] == b
                  and ((x["code"] == "2000") == (kind == "saldo"))]
            if not sl and not bl:
                continue
            su, bu = sum(usd(x) for x in sl), sum(usd(x) for x in bl)
            rec = {"period": p, "reference": ref, "tipo": kind, "seller": s, "buyer": b,
                   "seller_account": sl[0]["code"], "buyer_account": bl[0]["code"],
                   "seller_usd": str(q2(su)), "buyer_usd": str(q2(bu)),
                   "seller_rows": [x["source_row"] for x in sl], "buyer_rows": [x["source_row"] for x in bl]}
            if abs(su - bu) <= IC_TOLERANCE_USD:
                rec["eliminated_usd"] = str(q2(su))
                elims.append(rec)
                for x in sl + bl:
                    x["eliminated"] = True
            else:
                rec["difference_usd"] = str(q2(su - bu))
                discrepancies.append(rec)

    # consolidado esperado
    codes = [c[0] for c in CATALOG if not c[0].startswith("TOT")]
    cls = {c[0]: c[3] for c in CATALOG}
    consolidated, naive = {}, {}
    for p in PERIODS:
        inc = [x for x in all_lines if x["period"] == p and x["status"] in INCLUDED]
        by = {c: D(0) for c in codes}
        nv = {c: D(0) for c in codes}
        for x in inc:
            nv[x["code"]] += usd(x)
            by[x["code"]] += usd(x)
        for e in elims:
            if e["period"] == p:
                by[e["seller_account"]] -= D(e["eliminated_usd"])
                by[e["buyer_account"]] -= D(e["eliminated_usd"])

        def summ(m):
            ing = sum(m[c] for c in codes if cls[c] == "ingreso")
            costo = sum(m[c] for c in codes if cls[c] == "costo")
            gop = sum(m[c] for c in codes if cls[c] == "gasto_operativo")
            fin = sum(m[c] for c in codes if cls[c] == "gasto_financiero")
            imp = sum(m[c] for c in codes if cls[c] == "impuesto")
            act = sum(m[c] for c in codes if cls[c] == "activo")
            pas = sum(m[c] for c in codes if cls[c] == "pasivo")
            pat = sum(m[c] for c in codes if cls[c] == "patrimonio")
            ebit = ing - costo - gop
            return {"ingresos": ing, "costo_ventas": costo, "gastos_operativos": gop, "ebit": ebit,
                    "gastos_financieros": fin, "impuestos": imp, "utilidad_neta": ebit - fin - imp,
                    "activo_total": act, "pasivo_total": pas, "patrimonio": pat,
                    "activo_menos_pasivo_y_patrimonio": act - pas - pat}

        consolidated[p] = {"por_cuenta": {c: str(q2(v)) for c, v in by.items()},
                           "resumen": {k: str(q2(v)) for k, v in summ(by).items()},
                           "incompleto": p == "2026-11",
                           "empresas_faltantes": ["EMP006"] if p == "2026-11" else []}
        naive[p] = {k: str(q2(v)) for k, v in summ(nv).items()}

    status_count = {}
    for x in all_lines:
        status_count[x["status"]] = status_count.get(x["status"], 0) + 1

    return {
        "SINTETICO": True,
        "nota": "Clave calculada con Decimal desde la especificacion del generador, independiente del motor.",
        "seed": SEED,
        "convencion_tasa": "usd_por_unidad_local; importe_usd = importe_local x tasa",
        "tolerancia_intercompania_usd": str(IC_TOLERANCE_USD),
        "redondeo": "Decimal sin redondear internamente; se presenta a 2 decimales ROUND_HALF_UP",
        "reglas_de_inclusion": {"entran": sorted(INCLUDED),
                                "no_entran": ["excluded_duplicate", "pending_mapping", "blocked", "total"]},
        "conteo_registros_por_estado": status_count,
        "errores_sembrados": seeded,
        "eliminaciones_esperadas": elims,
        "discrepancias_esperadas": discrepancies,
        "consolidado_esperado_usd": consolidated,
        "suma_ingenua_sin_eliminar_usd": naive,
    }


def write_key_md(key, path):
    L = ["# ANSWER KEY - Grupo Ferrex (SINTETICO)", "",
         "Generado por `data/synthetic/generate.py`. No editar a mano.", "",
         "## Errores sembrados", "", "| # | Tipo | Empresa | Archivo | Hoja | Fila | Periodo |", "|---|---|---|---|---|---|---|"]
    for e in key["errores_sembrados"]:
        for u in e["ubicaciones"]:
            L.append(f"| {e['id']} | {e['tipo']} | {u['company_id']} | {u['file']} | {u.get('sheet') or '-'} "
                     f"| {u.get('row', '-')} | {u['period']} |")
    L += ["", "## Eliminaciones esperadas (USD)", "", "| Periodo | Ref | Tipo | Vendedor -> Comprador | Cuentas | USD |",
          "|---|---|---|---|---|---|"]
    for e in key["eliminaciones_esperadas"]:
        L.append(f"| {e['period']} | {e['reference']} | {e['tipo']} | {e['seller']} -> {e['buyer']} "
                 f"| {e['seller_account']} / {e['buyer_account']} | {e['eliminated_usd']} |")
    L += ["", "## Discrepancias (no se eliminan)", ""]
    for d in key["discrepancias_esperadas"]:
        L.append(f"- {d['period']} {d['reference']} ({d['tipo']}): {d['seller']} {d['seller_usd']} vs "
                 f"{d['buyer']} {d['buyer_usd']} -> diferencia {d['difference_usd']} USD")
    L += ["", "## Consolidado esperado (USD)", "", "| Concepto | " + " | ".join(PERIODS) + " |",
          "|---|" + "---|" * len(PERIODS)]
    for k in key["consolidado_esperado_usd"][PERIODS[0]]["resumen"]:
        L.append(f"| {k} | " + " | ".join(key["consolidado_esperado_usd"][p]["resumen"][k] for p in PERIODS) + " |")
    L += ["", "| Suma ingenua (sin eliminar) | " + " | ".join(PERIODS) + " |", "|---|" + "---|" * len(PERIODS)]
    for k in ("ingresos", "costo_ventas", "utilidad_neta"):
        L.append(f"| {k} | " + " | ".join(key["suma_ingenua_sin_eliminar_usd"][p][k] for p in PERIODS) + " |")
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


def main():
    rnd = random.Random(SEED)
    lines = build_lines(rnd)
    for cid, ls in lines.items():
        WRITERS[cid](ls, HERE / CO[cid]["file"])
    write_group_tables()
    KEY_DIR.mkdir(parents=True, exist_ok=True)
    key = build_answer_key(lines)
    (KEY_DIR / "answer_key.json").write_text(json.dumps(key, indent=2, ensure_ascii=False), encoding="utf-8")
    write_key_md(key, KEY_DIR / "ANSWER_KEY.md")
    print("OK: dataset SINTETICO generado en", HERE)


if __name__ == "__main__":
    main()
