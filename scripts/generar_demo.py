"""DATOS DE DEMO (SINTETICOS) - NO SON DATOS DEL RETO NI DE GRUPO AG.

Genera data/demo/: el mismo Grupo Ferrex de data/synthetic/, pero con DETALLE A NIVEL DE TRANSACCION
(facturas por cliente, compras por proveedor, planilla por departamento, saldos por banco y por cliente),
libros de Excel con formato (titulos, filtros, hoja de resumen con formulas, notas) y un juego de errores
NUEVO pensado para la presentacion, escondido dentro del detalle como pasaria en un archivo real.

5 de los 6 archivos traen 2 errores cada uno; el de Ferrex Importaciones (JSON) llega limpio.
Los totales por cuenta y mes son los mismos de la base, asi que el consolidado es reproducible.

Uso (desde la raiz del repo):
    python scripts/generar_demo.py

No modifica data/synthetic/ ni generate.py: los importa y reutiliza su especificacion.
La guia de cada error esta en data/demo/LEEME_DEMO.md.
"""
import csv
import datetime as dt
import importlib.util
import json
import random
import shutil
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

REPO = Path(__file__).resolve().parent.parent
SYN = REPO / "data" / "synthetic"
OUT = REPO / "data" / "demo"

_spec = importlib.util.spec_from_file_location("ferrex_generate", SYN / "generate.py")
G = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(G)
D = Decimal
C2 = D("0.01")
GROUP_TABLES = ["empresas.csv", "tasas.csv", "catalogo_cuentas.csv", "equivalencias.csv", "periodos.csv"]
DEMO_SEED = 1121


# ================================================================== 1) base limpia
def clean_base(lines):
    """Quita los 9 errores del dataset de desarrollo para que el demo solo tenga los suyos."""
    for cid in lines:
        out = []
        for x in lines[cid]:
            e = x.get("error")
            if e in (3, 4, 5):                                        # duplicados y cuenta sin mapear: fuera
                continue
            if e in (1, 7):                                           # moneda mal marcada -> funcional
                x["currency"] = G.CO[cid]["currency"]
            if e == 8:                                                # signo invertido -> positivo
                x["amount"] = abs(x["amount"])
            if e == 2:                                                # total que no cuadraba
                x["amount"] -= 5_000
            if e == 6 and cid == "EMP003":                            # IC: el comprador registra lo mismo
                x["amount"] = G.S(cid, 500_000)                       # 400,000 MXN x 0.05 = 20,000 USD
            x["error"], x["status"] = None, ("total" if x["kind"] == "total" else "ok")
            out.append(x)
        lines[cid] = out
    # mes faltante de Ferrex Importaciones: noviembre igual a octubre (sin la operacion intercompania)
    oct_ = [x for x in lines["EMP006"] if x["period"] == "2026-10"]
    nov = [dict(x, period="2026-11", date=G.last_day("2026-11")) for x in oct_ if not x["txn_id"]]
    lines["EMP006"] = oct_ + nov + [x for x in lines["EMP006"] if x["period"] != "2026-10"]
    return lines


def rebalance(lines):
    """Utilidades acumuladas (3100) = activo - pasivo - resto del patrimonio, por empresa y mes."""
    for ls in lines.values():
        for p in {x["period"] for x in ls}:
            bg = [x for x in ls if x["period"] == p and x["statement"] == "BG"]
            re_ = [x for x in bg if x["code"] == "3100"]
            if re_:
                act = sum(x["amount"] for x in bg if x["code"][0] == "1")
                pas = sum(x["amount"] for x in bg if x["code"][0] in "23" and x is not re_[0])
                re_[0]["amount"] = act - pas


# ================================================================== 2) detalle realista
# Por empresa y cuenta: (min, max) de lineas, descripciones, contrapartes (o None) y prefijo del documento.
GT_CLIENTES = ["Constructora Maya", "Ferreteria El Martillo", "Grupo Constructor Atlantico", "Ferromax Xela",
               "Materiales San Lucas", "Concretos del Pacifico", "Edificaciones Tikal", "Distribuidora La Torre",
               "Constructora Quetzal", "Inmobiliaria Cayala", "Ferreteria Los Altos", "Bloqueras Unidas"]
GT_PROV = ["Recicladora Centroamericana", "Siderurgica del Golfo", "Comercializadora de Aleaciones",
           "Gases Industriales de Guatemala", "Refractarios del Sur", "Energia Electrica de Guatemala"]
GT_TRANSP = ["Transportes Lopez", "Fletes Rapidos Chimaltenango", "Logistica Maya Express", "Carga Pesada GT"]
GT_BANCOS = ["Banco Industrial cta. monetaria 102-001234-5", "BAM cta. monetaria 900-12345-6",
             "Banrural cta. ahorro 3-445-12345-0", "Caja chica planta"]
MX_CLIENTES = ["Ferreteria La Esperanza", "Materiales y Aceros del Bajio", "Constructora Valle de Mexico",
               "Tlapaleria El Tornillo", "Grupo Edificador Monterrey", "Comercial Ferretera de Puebla",
               "Desarrollos Inmobiliarios Queretaro", "Ferremateriales Guadalajara"]
MX_PROV = ["Truper Distribucion", "Aceros Laminados del Norte", "Cementos y Agregados de Jalisco",
           "Pinturas Comex Mayoreo", "Herramientas Urrea Comercial", "Plasticos Rotomoldeados"]
SV_CLIENTES = ["Constructora Salvadorena", "Ferreteria Vidri Mayoreo", "Inversiones Santa Ana",
               "Materiales Freund Distribucion", "Edificaciones San Miguel", "Proyectos Habitacionales SV"]
SV_PROV = ["Importadora de Herramientas SV", "Distribuidora de Pinturas Centroamericana",
           "Ceramica del Pacifico", "Tuberias y Plasticos de El Salvador"]

SPEC = {
    "EMP001": {   # Aceros Ferrex: planta (descripciones ricas, columna Descripcion)
        "4000": (22, 32, ["Varilla corrugada 3/8\" grado 40", "Varilla corrugada 1/2\" grado 60",
                          "Alambre de amarre calibre 16", "Malla electrosoldada 6x6 10/10",
                          "Alambron 5.5 mm", "Varilla lisa 1/4\""], GT_CLIENTES, "FAC-A"),
        "5000": (10, 14, ["Chatarra ferrosa", "Palanquilla importada", "Energia electrica horno de arco",
                          "Ferroaleaciones (FeMn, FeSi)", "Electrodos de grafito", "Refractarios"], GT_PROV, "OC"),
        "6000": (4, 5, ["Planilla produccion", "Planilla administracion", "Planilla ventas",
                        "IGSS cuota patronal", "Provision Bono 14 y aguinaldo"], None, "PLA"),
        "6100": (2, 2, ["Alquiler bodega Km 17.5 ruta al Pacifico", "Alquiler bodega Villa Nueva"], None, "ALQ"),
        "6200": (6, 10, ["Flete varilla a cliente", "Flete de chatarra a planta", "Flete interdepartamental"],
                 GT_TRANSP, "FLT"),
        "6300": (5, 7, ["Seguridad privada", "Telefonia e internet", "Papeleria y utiles",
                        "Mantenimiento de montacargas", "Honorarios auditoria externa", "Agua y extraccion"],
                 None, "GV"),
        "6400": (3, 3, ["Depreciacion horno de arco", "Depreciacion tren de laminacion",
                        "Depreciacion vehiculos y montacargas"], None, "DEP"),
        "7000": (2, 2, ["Intereses prestamo Banco Industrial", "Intereses linea de credito BAM"], None, "INT"),
        "1000": (4, 4, GT_BANCOS, None, "EC"),
        "1100": (6, 8, ["Saldo por cobrar"], GT_CLIENTES, "CXC"),
        "2000": (4, 6, ["Saldo por pagar"], GT_PROV, "CXP"),
    },
    "EMP002": {   # Distribuidora Central (CSV sin columna de descripcion: el detalle va en contraparte)
        "4000": (24, 34, None, GT_CLIENTES, "FC"),
        "5000": (10, 14, None, ["Aceros Arquitectonicos", "Cementos Progreso Distribucion", "Tubovinil",
                                "Pinturas Centroamericanas", "Herramientas Truper Guatemala"], "OC"),
        "6000": (3, 4, None, None, "PLA"),
        "6200": (6, 9, None, GT_TRANSP, "FLT"),
        "6300": (4, 6, None, None, "GV"),
        "1000": (3, 3, None, None, "EC"),
        "1100": (6, 8, None, GT_CLIENTES, "CXC"),
    },
    "EMP003": {   # Ferrex Mexico: tiendas
        "4000": (18, 26, None, MX_CLIENTES, "CFDI-A"),
        "5000": (8, 12, None, MX_PROV, "OC-MX"),
        "6000": (3, 4, None, None, "NOM"),
        "6100": (4, 4, None, None, "ARR"),
        "6300": (4, 6, None, None, "GO"),
        "1100": (5, 7, None, MX_CLIENTES, "CXC"),
    },
    "EMP004": {   # Ferrex El Salvador (ingles); Rent no se desglosa (ahi va un error de moneda)
        "4000": (14, 20, None, SV_CLIENTES, "CCF"),
        "5000": (6, 9, None, SV_PROV, "PO"),
        "6000": (3, 4, None, None, "PAY"),
        "6300": (3, 5, None, None, "OPX"),
        "1100": (4, 6, None, SV_CLIENTES, "AR"),
    },
    "EMP005": {   # Transportes Ferrex: flota
        "4100": (16, 24, None, ["Ferrex Mexico Tienda Norte", "Cementos del Bajio", "Grupo Constructor Leon",
                                "Distribuidora Agricola del Centro", "Comercializadora Hidalguense"], "CP"),
        "6000": (3, 4, None, None, "NOM"),
        "6300": (6, 10, None, ["Gasolinera del Norte", "Pemex Estacion 4471", "Llantera Industrial Queretaro",
                               "Refaccionaria Diesel del Bajio"], "GTO"),
        "7000": (2, 2, None, None, "INT"),
    },
    "EMP006": {   # Ferrex Importaciones: importador
        "4000": (10, 14, None, ["Ferreteria Novey", "Do it Center Panama", "Cochez y Cia",
                                "Materiales Generales del Istmo", "Ferreteria Pacifico Colon"], "INV"),
        "5000": (5, 8, None, ["Stanley Black & Decker LatAm", "Bosch Power Tools", "Makita Distribution",
                              "Ningbo Hardware Export Co."], "PO"),
        "6000": (2, 3, None, None, "PAY"),
    },
}
NO_SPLIT_LOCAL = {"Mantenimiento de flota"}     # se deja una linea por mes (ahi se siembra el posible duplicado)


def split(amount, n, rnd):
    """Reparte un importe en n partes con centavos; la ultima absorbe la diferencia (suma exacta)."""
    w = [rnd.uniform(0.35, 1.65) for _ in range(n)]
    s = sum(w)
    parts = [(amount * D(str(x / s))).quantize(C2, ROUND_HALF_UP) for x in w[:-1]]
    return parts + [amount - sum(parts, D(0))]


def biz_day(period, rnd):
    y, m = map(int, period.split("-"))
    last = G.last_day(period).day
    while True:
        d = dt.date(y, m, rnd.randint(1, last))
        if d.weekday() < 5:
            return d


def explode(lines, rnd):
    for cid, ls in lines.items():
        spec, out, seq = SPEC.get(cid, {}), [], {}
        for x in ls:
            s = spec.get(x["code"])
            if (s is None or x["kind"] == "total" or x["txn_id"] or x["local_account"] in NO_SPLIT_LOCAL
                    or x["amount"] <= 0):
                out.append(x)
                continue
            lo, hi, descs, cps, pre = s
            n = rnd.randint(lo, hi)
            yymm = x["period"][2:].replace("-", "")
            rows = []
            for i, amt in enumerate(split(x["amount"], n, rnd)):
                seq[pre] = seq.get(pre, 0) + 1
                bg = x["statement"] == "BG"
                cp = rnd.choice(cps) if cps else None
                desc = descs[i % len(descs)] if descs else ""
                if cid == "EMP001" and cp and not bg:
                    desc = f"{desc} - {cp}"
                rows.append(dict(x, amount=amt, counterparty_text=cp, description=desc,
                                 txn_id=f"{pre}-{yymm}-{seq[pre]:04d}" if bg else f"{pre}-{seq[pre]:05d}",
                                 date=G.last_day(x["period"]) if bg else biz_day(x["period"], rnd)))
            out.extend(sorted(rows, key=lambda r: r["date"]))
        lines[cid] = out
    # descripciones del resto de lineas de Aceros Ferrex (la unica empresa con columna Descripcion)
    for x in lines["EMP001"]:
        if not x["description"]:
            x["description"] = {"8000": "ISR regimen sobre utilidades - pago trimestral",
                                "TOT_GOP": "Total gastos de operacion (subtotal de contabilidad)"}.get(
                x["code"], f"Saldo al cierre - {x['local_account']}")


# ================================================================== 3) errores de la demo
def pick(ls, period, code, rnd=None, **kw):
    c = [x for x in ls if x["period"] == period and x["code"] == code
         and all(x.get(k) == v for k, v in kw.items())]
    if not c:
        raise KeyError((period, code, kw))
    return rnd.choice(c) if rnd else c[0]


def seed_demo_errors(lines, rnd):
    errs = []

    # EMP001 Aceros Ferrex (XLSX) --------------------------------------------------------------
    L = lines["EMP001"]
    orig = pick(L, "2026-11", "4000", rnd, kind="normal", counterparty_id=None)
    dup = dict(orig)
    L.insert(L.index(orig) + 7, dup)                       # la misma factura, exportada otra vez mas abajo
    errs.append(("EMP001", f"Factura {orig['txn_id']} ({orig['counterparty_text']}, "
                           f"{orig['amount']:,.2f} GTQ) aparece dos veces (Nov)", "DUP-01"))
    tot = pick(L, "2026-12", "TOT_GOP")
    tot["amount"] += 12_000
    errs.append(("EMP001", "Total gastos de operacion de Dic declarado con 12,000 GTQ de mas", "TOT-01"))

    # EMP002 Distribuidora Central (CSV) ---------------------------------------------------------
    L = lines["EMP002"]
    q = pick(L, "2026-10", "6200", rnd)
    q["currency"] = "Q"
    errs.append(("EMP002", f"Flete {q['txn_id']} de Oct con moneda 'Q' en lugar de GTQ", "MON-01"))
    pl = [x for x in L if x["period"] == "2026-12" and x["code"] == "6000"]
    pl[-1]["amount"] += D(980_000) - sum(x["amount"] for x in pl)
    pl[-1]["txn_id"] = pl[-1]["txn_id"]
    errs.append(("EMP002", f"Planilla de Dic suma 980,000 GTQ, ~4.6 veces lo normal "
                           f"(la linea {pl[-1]['txn_id']} trae {pl[-1]['amount']:,.2f})", "ATI-01"))

    # EMP003 Ferrex Mexico (XLSX) ----------------------------------------------------------------
    L = lines["EMP003"]
    ref = pick(L, "2026-11", "7000")
    L.insert(L.index(ref) + 1, dict(ref, code="UNMAPPED", local_account="Comisiones bancarias",
                                    amount=D("38750.40"), txn_id="EC-BBVA-2611", counterparty_text=None))
    errs.append(("EMP003", "Cuenta nueva 'Comisiones bancarias' (38,750.40 MXN) sin equivalencia (Nov)", "MAP-01"))
    pick(L, "2026-12", "6200", txn_id="TF-IC-2612")["amount"] = D(196_000)
    errs.append(("EMP003", "Compra a Transportes Ferrex TF-IC-2612: 196,000 MXN contra 208,000 del vendedor", "IC-01"))

    # EMP004 Ferrex El Salvador (XLSX) -----------------------------------------------------------
    L = lines["EMP004"]
    neg = pick(L, "2026-10", "6000", rnd)
    neg["amount"] = -neg["amount"]
    errs.append(("EMP004", f"Linea de Payroll {neg['txn_id']} de Oct con signo negativo", "SIGN-01"))
    rent = pick(L, "2026-11", "6100")
    rent["amount"], rent["txn_id"] = D(160_000), "RENT-GT-1126"
    errs.append(("EMP004", "Rent de Nov = 160,000 'USD' (son quetzales: 160,000 x 0.125 = 20,000)", "ATI-01"))

    # EMP005 Transportes Ferrex (CSV) ------------------------------------------------------------
    L = lines["EMP005"]
    m = pick(L, "2026-12", "6300", local_account="Mantenimiento de flota")
    i = L.index(m)
    for _ in (1, 2):
        L.insert(i + 1, dict(m, amount=D("18400.00"), counterparty_text="Taller Mecanico Ruiz",
                             date=dt.date(2026, 12, 18), txn_id=None))
    m["amount"] -= D("36800.00")
    errs.append(("EMP005", "Dos cargos de 18,400 MXN al Taller Mecanico Ruiz el 18/12, sin num_doc", "DUP-02"))
    intr = pick(L, "2026-11", "7000", rnd)
    s = f"{intr['amount']:.2f}"
    intr["raw_amount"] = s.replace("0", "O", 1) if "0" in s else s[:1] + "O" + s[2:]
    errs.append(("EMP005", f"Intereses {intr['txn_id']} de Nov con importe '{intr['raw_amount']}' "
                           "(letra O en lugar de cero)", "ING-01"))
    return errs


# ================================================================== 4) escritura con formato
HEAD_FILL = PatternFill("solid", fgColor="1F3864")
HEAD_FONT = Font(bold=True, color="FFFFFF")
TITLE_FONT = Font(bold=True, size=14)
SUB_FONT = Font(italic=True, color="555555")
THIN = Border(bottom=Side(style="thin", color="BFBFBF"))
NUM = '#,##0.00;[Red]-#,##0.00'
ORDER = {"ER": 0, "BG": 1}


def ordered(ls):
    return sorted(ls, key=lambda x: (x["period"], ORDER[x["statement"]]))


def sheet_table(ws, titles, header, rows, widths, num_cols=(), date_cols=()):
    for i, t in enumerate(titles):
        ws.append([t])
        ws.cell(ws.max_row, 1).font = TITLE_FONT if i == 0 else SUB_FONT
    if titles:
        ws.append([])
    ws.append(header)
    h = ws.max_row
    for c in range(1, len(header) + 1):
        cell = ws.cell(h, c)
        cell.fill, cell.font, cell.alignment = HEAD_FILL, HEAD_FONT, Alignment(horizontal="center")
    for r in rows:
        ws.append(r)
        for c in num_cols:
            ws.cell(ws.max_row, c).number_format = NUM
        for c in date_cols:
            ws.cell(ws.max_row, c).number_format = "dd/mm/yyyy"
        for c in range(1, len(header) + 1):
            ws.cell(ws.max_row, c).border = THIN
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = ws.cell(h + 1, 1)
    ws.auto_filter.ref = f"A{h}:{get_column_letter(len(header))}{ws.max_row}"
    return h


def summary_sheet(wb, data_ws, h, last, acc_col, amt_col, per_col, accounts, months, title):
    """Hoja de resumen con formulas SUMIFS (Excel las calcula al abrir; el motor no lee esta hoja)."""
    ws = wb.create_sheet("Resumen")
    ws.append([title])
    ws["A1"].font = TITLE_FONT
    ws.append(["Formulas sobre la hoja de detalle. Solo de consulta."])
    ws["A2"].font = SUB_FONT
    ws.append([])
    ws.append(["Cuenta local"] + [lbl for lbl, _ in months])
    for c in range(1, len(months) + 2):
        cell = ws.cell(4, c)
        cell.fill, cell.font = HEAD_FILL, HEAD_FONT
    rng = lambda col: f"'{data_ws.title}'!${col}${h + 1}:${col}${last}"
    for a in accounts:
        ws.append([a])
        r = ws.max_row
        for j, (_, crit) in enumerate(months, start=2):
            ws.cell(r, j, f"=SUMIFS({rng(amt_col)},{rng(acc_col)},$A{r},{crit(rng(per_col))})")
            ws.cell(r, j).number_format = NUM
    ws.column_dimensions["A"].width = 38
    for j in range(2, len(months) + 2):
        ws.column_dimensions[get_column_letter(j)].width = 16


def date_months(rngf):
    out = []
    for p, lbl in (("2026-10", "Oct 2026"), ("2026-11", "Nov 2026"), ("2026-12", "Dic 2026 (ppto)")):
        y, m = map(int, p.split("-"))
        e = G.last_day(p)
        out.append((lbl, lambda r, y=y, m=m, e=e: f"{r},\">=\"&DATE({y},{m},1),{r},\"<=\"&DATE({e.year},{e.month},{e.day})"))
    return out


def as_dt(d):
    return dt.datetime.combine(d, dt.time())


def write_emp001(ls, path):
    wb = Workbook()
    ws = wb.active
    ws.title = "Presupuesto"
    rows = [[as_dt(x["date"]), x["local_account"], x["description"], float(x["amount"]), x["currency"],
             x["counterparty_text"], x["txn_id"]] for x in ordered(ls)]
    h = sheet_table(ws, ["ACEROS FERREX, S.A.", "Libro de presupuesto y ejecucion por documento - Oct a Dic 2026",
                         "Cifras en quetzales (GTQ). Diciembre 2026 es presupuesto. Fuente: ERP planta Escuintla."],
                    ["Período", "Cuenta", "Descripción", "Monto", "Moneda", "Contraparte", "No. Factura"],
                    rows, [12, 30, 62, 16, 9, 30, 16], num_cols=(4,), date_cols=(1,))
    accs = list(dict.fromkeys(x["local_account"] for x in ordered(ls)))
    summary_sheet(wb, ws, h, ws.max_row, "B", "D", "A", accs, date_months(None), "Resumen por cuenta (GTQ)")
    n = wb.create_sheet("Notas")
    for t in ["Notas de contabilidad", "- Ingresos y costos a nivel de factura / orden de compra.",
              "- Saldos de balance al ultimo dia del mes.", "- La fila 'Total gastos de operacion' es un control "
              "manual de contabilidad.", "Preparado por: Contabilidad Aceros Ferrex"]:
        n.append([t])
    wb.save(path)


def write_emp002(ls, path):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["periodo", "cuenta", "importe", "moneda", "contraparte", "referencia"])
        for x in ordered(ls):
            w.writerow([x["date"].strftime("%d/%m/%Y"), x["local_account"], G.fmt_es(x["amount"]), x["currency"],
                        x["counterparty_text"] or "", x["txn_id"] or ""])


def write_emp003(ls, path):
    wb = Workbook()
    ws = wb.active
    ws.title = "Presupuesto MX"
    rows = []
    for x in ordered(ls):
        y, m = x["period"].split("-")
        rows.append([f"{G.MES_ES[m]} {y}", x["local_account"], float(x["amount"]), x["currency"],
                     x["counterparty_text"], x["txn_id"]])
    h = sheet_table(ws, ["Ferrex México S. de R.L. de C.V.",
                         "Presupuesto y cifras reales - expresado en Pesos mexicanos (MXN)",
                         "Auxiliar por documento (CFDI / orden de compra). Dic-2026 = presupuesto."],
                    ["Mes", "Cuenta contable", "Valor", "Divisa", "Empresa relacionada", "Documento"],
                    rows, [11, 34, 16, 8, 34, 16], num_cols=(3,))
    accs = list(dict.fromkeys(x["local_account"] for x in ordered(ls)))
    months = [(f"{G.MES_ES[p[5:]]} 2026", lambda r, p=p: f"{r},\"{G.MES_ES[p[5:]]} 2026\"")
              for p in ("2026-10", "2026-11", "2026-12")]
    summary_sheet(wb, ws, h, ws.max_row, "B", "C", "A", accs, months, "Resumen por cuenta (MXN)")
    wb.save(path)


def write_emp004(ls, path):
    wb = Workbook()
    er = wb.active
    er.title = "Income Statement"
    bg = wb.create_sheet("Balance Sheet")
    hdr = ["Period", "Account", "Amount", "Currency", "Counterparty", "Invoice ID"]
    for ws, st, sub in ((er, "ER", "Income statement detail by document"),
                        (bg, "BG", "Balance sheet - month-end balances")):
        rows = [[as_dt(x["date"]), x["local_account"], float(x["amount"]), x["currency"], x["counterparty_text"],
                 x["txn_id"]] for x in ordered(ls) if x["statement"] == st]
        sheet_table(ws, ["FERREX EL SALVADOR, S.A. DE C.V.", f"{sub} - Oct to Dec 2026 (USD)"],
                    hdr, rows, [12, 34, 16, 9, 34, 16], num_cols=(3,), date_cols=(1,))
    n = wb.create_sheet("Notes")
    for t in ["Figures in US dollars. December 2026 is budget.", "Rent of the San Salvador warehouse is paid "
              "through the Guatemala office.", "Prepared by: Finance SV"]:
        n.append([t])
    wb.save(path)


def write_emp005(ls, path):
    with open(path, "w", encoding="cp1252", newline="") as f:
        w = csv.writer(f, delimiter=",")
        w.writerow(["fecha", "cuenta", "monto", "moneda", "cia_relacionada", "num_doc"])
        for x in ordered(ls):
            w.writerow([x["date"].strftime("%d/%m/%Y"), x["local_account"],
                        x.get("raw_amount") or f"{x['amount']:.2f}", x["currency"],
                        x["counterparty_text"] or "", x["txn_id"] or ""])


def write_emp006(ls, path):
    entries = [{"period": x["date"].isoformat(), "account": x["local_account"], "amount": float(x["amount"]),
                "counterparty": x["counterparty_text"], "transaction_id": x["txn_id"]} for x in ordered(ls)]
    doc = {"company_name": G.CO["EMP006"]["name"], "country": "Panama", "reporting_currency": "USD",
           "source_system": "SAP Business One - export", "scenario_note": "2026-12 is budget",
           "generated_at": "2026-11-20T18:42:00-05:00", "entries": entries}
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")


WRITERS = {"EMP001": write_emp001, "EMP002": write_emp002, "EMP003": write_emp003,
           "EMP004": write_emp004, "EMP005": write_emp005, "EMP006": write_emp006}


def main():
    rnd = random.Random(DEMO_SEED)
    lines = clean_base(G.build_lines(random.Random(G.SEED)))
    rebalance(lines)
    explode(lines, rnd)
    errs = seed_demo_errors(lines, rnd)
    OUT.mkdir(parents=True, exist_ok=True)
    for cid, ls in lines.items():
        WRITERS[cid](ls, OUT / G.CO[cid]["file"])
    for t in GROUP_TABLES:
        shutil.copyfile(SYN / t, OUT / t)
    print("OK: datos de DEMO (sinteticos) generados en", OUT)
    for cid, ls in lines.items():
        print(f"  {cid}  {G.CO[cid]['file']:<32} {len(ls):>4} filas")
    for cid, what, rule in errs:
        print(f"  {cid}  [{rule}]  {what}")


if __name__ == "__main__":
    main()
