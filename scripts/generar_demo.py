"""DATOS DE DEMO (SINTETICOS) - NO SON DATOS DEL RETO NI DE GRUPO AG.

Genera data/demo/: el mismo Grupo Ferrex de data/synthetic/, pero con un juego de errores NUEVO pensado
para la presentacion. 5 de los 6 archivos traen 2 errores cada uno; el de Ferrex Importaciones (JSON)
llega limpio para mostrar que un archivo correcto entra sin alertas.

Uso (desde la raiz del repo):
    python scripts/generar_demo.py

No modifica data/synthetic/ ni generate.py: los importa y reutiliza sus escritores de archivos.
La guia de cada error esta en data/demo/LEEME_DEMO.md.
"""
import csv
import datetime as dt
import importlib.util
import random
import shutil
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SYN = REPO / "data" / "synthetic"
OUT = REPO / "data" / "demo"

_spec = importlib.util.spec_from_file_location("ferrex_generate", SYN / "generate.py")
G = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(G)
D = Decimal
GROUP_TABLES = ["empresas.csv", "tasas.csv", "catalogo_cuentas.csv", "equivalencias.csv", "periodos.csv"]


# ------------------------------------------------------------------ 1) base limpia
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
    nov = []
    for x in lines["EMP006"]:
        if x["period"] == "2026-10" and not x["txn_id"]:
            y = dict(x, period="2026-11", date=G.last_day("2026-11"))
            nov.append(y)
    oct_ = [x for x in lines["EMP006"] if x["period"] == "2026-10"]
    rest = [x for x in lines["EMP006"] if x["period"] != "2026-10"]
    lines["EMP006"] = oct_ + nov + rest
    return lines


def rebalance(lines):
    """Utilidades acumuladas (3100) = activo - pasivo - resto del patrimonio, por empresa y mes."""
    for cid, ls in lines.items():
        for p in {x["period"] for x in ls}:
            bg = [x for x in ls if x["period"] == p and x["statement"] == "BG"]
            re_ = [x for x in bg if x["code"] == "3100"]
            if not re_:
                continue
            act = sum(x["amount"] for x in bg if x["code"][0] == "1")
            pas = sum(x["amount"] for x in bg if x["code"][0] in "23" and x is not re_[0])
            re_[0]["amount"] = act - pas


# ------------------------------------------------------------------ 2) errores de la demo
def find(ls, period, code, **kw):
    for x in ls:
        if x["period"] == period and x["code"] == code and all(x.get(k) == v for k, v in kw.items()):
            return x
    raise KeyError((period, code, kw))


def insert_after(ls, ref, new):
    ls.insert(ls.index(ref) + 1, new)


def seed_demo_errors(lines):
    errs = []

    # EMP001 Aceros Ferrex (XLSX) ------------------------------------------------------------
    L = lines["EMP001"]
    ref = find(L, "2026-11", "4000", txn_id=None)
    for i in (2, 1):
        insert_after(L, ref, G.line("EMP001", "2026-11", "4000", 65_000, cp_text="Constructora Quetzal",
                                    txn="FAC-B-1120", desc="Venta a Constructora Quetzal",
                                    date=G.last_day("2026-11")))
    errs.append(("EMP001", "Factura FAC-B-1120 registrada dos veces (Nov)", "DUP-01"))
    tot = find(L, "2026-12", "TOT_GOP")
    tot["amount"] += 12_000
    errs.append(("EMP001", "Total gastos de operacion de Dic no cuadra (+12,000 GTQ)", "TOT-01"))

    # EMP002 Distribuidora Central (CSV) ------------------------------------------------------
    L = lines["EMP002"]
    find(L, "2026-10", "6200")["currency"] = "QTZ"
    errs.append(("EMP002", "Moneda 'QTZ' (no existe) en Transporte de Oct", "MON-01"))
    find(L, "2026-12", "6000")["amount"] = D(980_000)
    errs.append(("EMP002", "Planilla de Dic = 980,000 GTQ, ~4 veces su nivel habitual", "ATI-01"))

    # EMP003 Ferrex Mexico (XLSX) -------------------------------------------------------------
    L = lines["EMP003"]
    insert_after(L, find(L, "2026-11", "7000"),
                 G.line("EMP003", "2026-11", "UNMAPPED", 40_000, local="Comisiones bancarias"))
    errs.append(("EMP003", "Cuenta 'Comisiones bancarias' sin equivalencia en el catalogo (Nov)", "MAP-01"))
    find(L, "2026-12", "6200", txn_id="TF-IC-2612")["amount"] = D(196_000)
    errs.append(("EMP003", "Compra a Transportes Ferrex TF-IC-2612: 196,000 MXN vs 208,000 del vendedor", "IC-01"))

    # EMP004 Ferrex El Salvador (XLSX) --------------------------------------------------------
    L = lines["EMP004"]
    x = find(L, "2026-10", "6000")
    x["amount"] = -x["amount"]
    errs.append(("EMP004", "Payroll de Oct con signo negativo", "SIGN-01"))
    find(L, "2026-11", "6100")["amount"] = D(160_000)
    errs.append(("EMP004", "Rent de Nov = 160,000 'USD' (son quetzales: 160,000 x 0.125 = 20,000)", "ATI-01"))

    # EMP005 Transportes Ferrex (CSV) ---------------------------------------------------------
    L = lines["EMP005"]
    ref = find(L, "2026-12", "6300", local_account="Mantenimiento de flota")
    for _ in (1, 2):
        insert_after(L, ref, G.line("EMP005", "2026-12", "6300b", 18_400, cp_text="Taller Mecanico Ruiz",
                                    date=dt.date(2026, 12, 18)))
    errs.append(("EMP005", "Dos cargos de 18,400 MXN al Taller Mecanico Ruiz el 18/12 sin documento", "DUP-02"))
    find(L, "2026-11", "7000")["raw_amount"] = "7O000.00"          # letra O en lugar de cero
    errs.append(("EMP005", "Intereses de Nov con importe '7O000.00' (letra O)", "ING-01"))
    return errs


def write_emp005(lines, path):
    """Igual al escritor de generate.py, pero respeta un importe crudo (texto) para sembrar el error."""
    with open(path, "w", encoding="cp1252", newline="") as f:
        w = csv.writer(f, delimiter=",")
        w.writerow(["fecha", "cuenta", "monto", "moneda", "cia_relacionada", "num_doc"])
        for x in lines:
            w.writerow([x["date"].strftime("%d/%m/%Y"), x["local_account"],
                        x.get("raw_amount") or f"{x['amount']:.2f}", x["currency"],
                        x["counterparty_text"] or "", x["txn_id"] or ""])


def main():
    lines = clean_base(G.build_lines(random.Random(G.SEED)))
    rebalance(lines)
    errs = seed_demo_errors(lines)
    OUT.mkdir(parents=True, exist_ok=True)
    for cid, ls in lines.items():
        writer = write_emp005 if cid == "EMP005" else G.WRITERS[cid]
        writer(ls, OUT / G.CO[cid]["file"])
    for t in GROUP_TABLES:
        shutil.copyfile(SYN / t, OUT / t)
    print("OK: datos de DEMO (sinteticos) generados en", OUT)
    for cid, what, rule in errs:
        print(f"  {cid}  [{rule}]  {what}")


if __name__ == "__main__":
    main()
