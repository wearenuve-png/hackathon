"""Genera data/demo_errores/: los mismos 6 archivos y formatos que data/synthetic (Excel, CSV, JSON) mas sus
perfiles, pero con 7 errores sembrados, visibles al abrir el archivo. Parte de una COPIA de data/synthetic (que no se
modifica) y es reproducible: semilla fija.

    .venv/bin/python scripts/generate_demo_errores.py

DATOS SINTETICOS. data/synthetic ya trae sus 9 errores base (tests/fixtures/ANSWER_KEY.md); aqui se AGREGAN 7 mas, de
modo que la diferencia entre los dos escenarios son exactamente estos 7."""
import csv
import datetime as dt
import io
import json
import random
import shutil
import sys
from decimal import Decimal
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "synthetic"
OUT = ROOT / "data" / "demo_errores"
PROFILES = ROOT / "profiles"
SEED = 2027
D = Decimal


def copiar():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    for f in SRC.iterdir():
        if f.is_file() and f.name not in ("generate.py", "README_SINTETICO.md"):
            shutil.copy2(f, OUT / f.name)
    (OUT / "perfiles").mkdir()
    for f in PROFILES.glob("*.json"):
        shutil.copy2(f, OUT / "perfiles" / f.name)


def _csv_lines(path, enc):
    return path.read_bytes().decode(enc).splitlines(keepends=True)


def main():
    rnd = random.Random(SEED)
    copiar()
    key = {"semilla": SEED, "base": "data/synthetic (con sus 9 errores base, no tocada)", "errores": []}

    # ---- 2. casilla de monto en blanco (EMP002, CSV ';' con coma decimal)
    f = OUT / "distribuidora_central_gt.csv"
    lines = _csv_lines(f, "utf-8")
    cuenta = rnd.choice(["Gastos varios", "Transporte"])
    idx = next(i for i, ln in enumerate(lines) if ln.startswith(f"10/2026;{cuenta};"))
    partes = lines[idx].rstrip("\r\n").split(";")
    original = partes[2]
    otros = [D(ln.split(";")[2].replace(".", "").replace(",", ".")) for ln in lines
             if ln.split(";")[1:2] == [cuenta] and not ln.startswith("10/2026")]
    otros.sort()
    propuesto = (otros[0] + otros[-1]) / 2 if len(otros) == 2 else otros[len(otros) // 2]
    partes[2] = ""
    lines[idx] = ";".join(partes) + "\n"
    f.write_text("".join(lines), encoding="utf-8")
    original_gtq = D(original.replace(".", "").replace(",", "."))
    key["errores"].append({"n": 2, "empresa": "EMP002", "archivo": f.name, "hoja": None, "fila": idx + 1,
                           "que_es": f"Casilla de monto en blanco: «{cuenta}» de 2026-10 (era {original} GTQ).",
                           "regla": "ING-01", "accion": "PROPUESTA", "valor_leido": "(vacio)",
                           "valor_propuesto": str(propuesto), "moneda": "GTQ", "usd_propuesto": str(propuesto * D("0.125")),
                           "usd_original": str(original_gtq * D("0.125")),
                           "propuesta": "Usar la mediana del mismo rubro en los otros periodos (referencia, no certeza).",
                           "cuenta": cuenta})

    # ---- 1. fila duplicada con el mismo ID (EMP003, XLSX)
    f = OUT / "ferrex_mexico.xlsx"
    wb = load_workbook(f)
    ws = wb["Presupuesto MX"]
    for _ in range(2):
        ws.append(["Oct 2026", "Ingresos netos", 60000, "MXN", None, "FAC-M-0902"])
    fila = ws.max_row
    wb.save(f)
    key["errores"].append({"n": 1, "empresa": "EMP003", "archivo": f.name, "hoja": "Presupuesto MX",
                           "fila": f"{fila - 1} y {fila}", "que_es": "Factura FAC-M-0902 dos veces (60,000 MXN = 3,000 USD).",
                           "regla": "DUP-01", "accion": "APLICADA_AUTOMATICAMENTE", "valor_leido": "60000 / 60000",
                           "valor_propuesto": None, "moneda": "MXN", "usd_propuesto": "3000", "usd_excluido": "3000",
                           "propuesta": "Se excluye la 2.a fila con un ajuste registrado y reversible."})

    # ---- 3. texto en un campo numerico (EMP005, CSV ',' con punto decimal, cp1252)
    f = OUT / "transportes_ferrex_mx.csv"
    raw = f.read_bytes()
    nl = "\r\n" if b"\r\n" in raw else "\n"
    txt = raw.decode("cp1252")
    nlin = len(txt.splitlines()) + 1
    buf = io.StringIO()
    csv.writer(buf, lineterminator=nl).writerow(["31/10/2026", "Combustible y lubricantes", "1O,000", "MXN", "", ""])
    txt = (txt if txt.endswith(("\n", "\r")) else txt + nl) + buf.getvalue()
    f.write_bytes(txt.encode("cp1252"))
    key["errores"].append({"n": 3, "empresa": "EMP005", "archivo": f.name, "hoja": None, "fila": nlin,
                           "que_es": "Texto en un campo numerico: «1O,000» (letra O en vez de cero).",
                           "regla": "ING-01", "accion": "PROPUESTA", "valor_leido": "1O,000",
                           "valor_propuesto": "10000", "moneda": "MXN", "usd_propuesto": "500",
                           "propuesta": "Cambiar la letra O por el cero: 10,000 MXN.", "cuenta": "Combustible y lubricantes"})

    # ---- 4. archivo que declara USD siendo empresa GTQ (EMP001, XLSX)
    f = OUT / "aceros_ferrex_gt.xlsx"
    wb = load_workbook(f)
    ws = wb["Presupuesto"]
    n = 0
    for r in ws.iter_rows(min_row=2):
        if r[4].value == "GTQ":
            r[4].value = "USD"
            n += 1
    wb.save(f)
    key["errores"].append({"n": 4, "empresa": "EMP001", "archivo": f.name, "hoja": "Presupuesto",
                           "fila": f"2 a {ws.max_row} (columna Moneda, {n} filas)",
                           "que_es": "El archivo declara USD en todas sus filas, pero el perfil de la empresa dice GTQ.",
                           "regla": "CARGA-01", "accion": "PROPUESTA", "valor_leido": "USD", "valor_propuesto": "GTQ",
                           "moneda": "GTQ", "propuesta": "Procesar el archivo con la moneda del perfil (GTQ)."})

    # ---- 5. signo invertido en un registro de 4,000 (EMP004, XLSX)
    f = OUT / "ferrex_el_salvador.xlsx"
    wb = load_workbook(f)
    ws = wb["Income Statement"]
    ws.append([dt.datetime(2026, 10, 31), "Other operating expenses", -4000, "USD", None, None])
    fila = ws.max_row
    wb.save(f)
    key["errores"].append({"n": 5, "empresa": "EMP004", "archivo": f.name, "hoja": "Income Statement", "fila": fila,
                           "que_es": "Gasto de 4,000 USD con signo negativo (-4,000).", "regla": "SIGN-01",
                           "accion": "PROPUESTA", "valor_leido": "-4000", "valor_propuesto": "4000", "moneda": "USD",
                           "usd_propuesto": "4000", "propuesta": "Corregir el signo: +4,000 USD.",
                           "cuenta": "Other operating expenses"})

    # ---- 6. asiento omitido de 8,000 que descuadra el balance (EMP006, JSON)
    f = OUT / "ferrex_importaciones_pa.json"
    doc = json.loads(f.read_text(encoding="utf-8"))
    doc["entries"].append({"period": "2026-12", "account": "Trade payables", "amount": 8000, "counterparty": None,
                           "transaction_id": None})
    f.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    key["errores"].append({"n": 6, "empresa": "EMP006", "archivo": f.name, "hoja": "entries", "fila": len(doc["entries"]),
                           "que_es": "Falta el lado de activo de un asiento de 8,000 USD: solo esta «Trade payables» "
                                     "(pasivo +8,000). Activo - (pasivo + patrimonio) = -8,000 USD en 2026-12.",
                           "regla": "BAL-01", "accion": "PROPUESTA", "valor_leido": "8000", "valor_propuesto": "8000",
                           "moneda": "USD", "diferencia_balance": "-8000", "usd_propuesto": "8000",
                           "propuesta": "Agregar el asiento omitido por 8,000 USD en la cuenta de activo que elija una persona."})

    # ---- 7. tasa de cambio mal escrita (tasas.csv): MXN 2026-12 = 0.525 en vez de 0.0525
    f = OUT / "tasas.csv"
    lineas = f.read_text(encoding="utf-8").splitlines(keepends=True)
    i = next(i for i, ln in enumerate(lineas) if ln.startswith("2026-12,MXN,"))
    lineas[i] = "2026-12,MXN,0.525\n"
    f.write_text("".join(lineas), encoding="utf-8")
    key["errores"].append({"n": 7, "empresa": "GRUPO", "archivo": f.name, "hoja": None, "fila": i + 1,
                           "que_es": "Tasa MXN de 2026-12 escrita 0.525 en vez de 0.0525 (decimal corrido: x10).",
                           "regla": "TAS-01", "accion": "PROPUESTA", "valor_leido": "0.525", "valor_propuesto": "0.0525",
                           "moneda": "MXN", "propuesta": "Corregir a 0.0525 (decimal corrido; queda a 5 % de la tasa del mes anterior)."})

    key["errores"].sort(key=lambda e: e["n"])
    # Efecto esperado en 2026-10 (respecto a data/synthetic) al APROBAR las propuestas de #2, #3 y #5 (el #1 deja
    # 3,000 USD de ingresos una sola vez). El #2 REEMPLAZA un importe de 5,000 USD, por eso suma solo la diferencia.
    e2, e3, e5 = (next(e for e in key["errores"] if e["n"] == n) for n in (2, 3, 5))
    gastos = (D(e2["usd_propuesto"]) - D(e2["usd_original"])) + D(e3["usd_propuesto"]) + D(e5["usd_propuesto"])
    key["delta_oct_tras_aprobar"] = {"ingresos": "3000", "gastos_operativos": str(gastos),
                                     "utilidad_neta": str(D(3000) - gastos)}
    (OUT / "ANSWER_KEY.json").write_text(json.dumps(key, indent=2, ensure_ascii=False), encoding="utf-8")
    md = ["# ANSWER KEY - data/demo_errores (SINTETICO)", "",
          "Generado por `scripts/generate_demo_errores.py` (semilla %d). No editar a mano." % SEED, "",
          "Parte de una copia de `data/synthetic`, que **ya trae sus 9 errores base** (`tests/fixtures/ANSWER_KEY.md`) y "
          "no se modifica. Aqui se **agregan 7 errores**; la diferencia entre los dos escenarios son exactamente estos.", "",
          "Acciones: **APLICADA_AUTOMATICAMENTE** = solo el duplicado exacto con el mismo ID (se excluye con un ajuste "
          "registrado y reversible). **PROPUESTA** = todo lo demas: el registro queda bloqueado o pendiente y NEXUS "
          "propone una correccion que una persona aprueba o rechaza; el archivo fuente nunca se modifica.", "",
          "| # | Empresa | Archivo | Hoja | Fila | Que es | Regla | Accion | Valor leido | Valor propuesto |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for e in key["errores"]:
        md.append(f"| {e['n']} | {e['empresa']} | {e['archivo']} | {e['hoja'] or '-'} | {e['fila']} | {e['que_es']} | "
                  f"{e['regla']} | {e['accion']} | {e['valor_leido']} | {e['valor_propuesto'] or '-'} |")
    md += ["", "## Que debe hacer NEXUS con cada uno", ""]
    for e in key["errores"]:
        md.append(f"{e['n']}. **{e['regla']}**: {e['propuesta']}")
    md += ["", "## Efectos en cascada (consecuencias, no errores nuevos)", "",
           "- **#4** deja la carga de EMP001 en revision: EMP001 no aporta registros y las operaciones intercompania con "
           "EMP002 quedan sin pareja hasta aprobar la correccion.",
           "- **#7** multiplica por 10 todo lo valorado en MXN en 2026-12 y puede disparar tambien alertas de importe atipico "
           "de EMP003 y EMP005 en ese periodo; desaparecen al aprobar la tasa corregida.",
           "- **#6** solo se ve en 2026-12 de EMP006 (balance); no cambia el estado de resultados."]
    (OUT / "ANSWER_KEY.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("OK: escenario con errores generado en", OUT)


if __name__ == "__main__":
    main()
