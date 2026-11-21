"""Grupo ficticio: 6 empresas, 3 monedas, errores sembrados. Sirve para probar el motor
mientras no llegan los archivos reales (el lector real solo debe producir este mismo esquema)."""
import random
import pandas as pd

from .modelos import COLUMNAS

MESES = [f"2026-{m:02d}" for m in range(1, 13)]
TASAS = {"USD": 1.0, "GTQ": 8.0, "MXN": 20.0}

# empresa: (moneda real, ingreso mensual tipico en USD)
EMPRESAS = {"A": ("GTQ", 100_000), "B": ("MXN", 100_000), "C": ("USD", 150_000),
            "D": ("GTQ", 120_000), "E": ("GTQ", 80_000), "F": ("USD", 60_000)}

# Verdad de referencia: (empresa, regla) que el validador DEBE encontrar
CATALOGO = [
    ("A", "intercompania.diferencia"),
    ("C", "integridad.total_descuadrado"),
    ("D", "moneda.equivocada"),
    ("E", "contable.balance_descuadrado"),
    ("E", "integridad.duplicado"),
    ("E", "estructura.monto_no_numerico"),
    ("F", "integridad.signo_invertido"),
    ("F", "integridad.mes_faltante"),
    ("F", "intercompania.sin_contraparte"),
    ("F", "razonabilidad.variacion_atipica"),
]
LIMPIAS = ["B"]  # no debe tener hallazgos


def generar(seed=7):
    rnd = random.Random(seed)
    filas = []
    contador = {}

    def add(e, archivo, periodo, concepto, tipo, monto, moneda, contraparte=None, grupo=None):
        contador[e] = contador.get(e, 1) + 1  # la fila 1 es el encabezado
        filas.append(dict(archivo=archivo, empresa=e, periodo=periodo, concepto=concepto, tipo=tipo,
                          monto=monto, fila=contador[e], moneda=moneda, contraparte=contraparte, grupo=grupo))

    for e, (mon_real, base_usd) in EMPRESAS.items():
        archivo = f"presupuesto_{e}.xlsx"
        k = TASAS[mon_real]
        mon_decl = "USD" if e == "D" else mon_real   # D declara USD pero reporta GTQ
        for p in MESES:
            if e == "F" and p == "2026-11":
                continue                                  # mes faltante
            ing = base_usd * k * rnd.uniform(0.93, 1.07)
            if e == "F" and p == "2026-10":
                ing *= 4                                  # variacion atipica
            ventas, serv = round(ing * 0.7, 2), round(ing * 0.3, 2)
            costo, gasto = round(ing * 0.6, 2), round(ing * 0.25, 2)
            util = round(ventas + serv - costo - gasto, 2)
            activo, pasivo = round(ing * 3, 2), round(ing * 1.8, 2)
            patrimonio = round(activo - pasivo, 2)
            tot = round(ventas + serv, 2)

            if e == "C" and p == "2026-06":
                tot += 10_000 * k                         # total no cuadra
            if e == "E" and p == "2026-08":
                activo += 20_000 * k                      # balance descuadrado
            if e == "F" and p == "2026-04":
                costo = -costo                            # signo invertido

            add(e, archivo, p, "Ventas producto", "ingreso", ventas, mon_decl, grupo="ingreso")
            if e == "E" and p == "2026-02":
                add(e, archivo, p, "Ventas producto", "ingreso", ventas, mon_decl, grupo="ingreso")  # duplicado
            add(e, archivo, p, "Servicios", "ingreso", serv, mon_decl, grupo="ingreso")
            add(e, archivo, p, "Total ingresos", "total", round(tot, 2), mon_decl, grupo="ingreso")
            add(e, archivo, p, "Costo de ventas", "costo", costo, mon_decl)
            gasto_val = "N/A" if (e == "E" and p == "2026-09") else gasto
            add(e, archivo, p, "Gastos operativos", "gasto", gasto_val, mon_decl)
            add(e, archivo, p, "Utilidad", "utilidad", util, mon_decl)
            add(e, archivo, p, "Activo total", "activo", activo, mon_decl)
            add(e, archivo, p, "Pasivo total", "pasivo", pasivo, mon_decl)
            add(e, archivo, p, "Patrimonio", "patrimonio", patrimonio, mon_decl)

    def ic(e, p, tipo, concepto, monto_local, contra):
        add(e, f"presupuesto_{e}.xlsx", p, concepto, tipo, monto_local,
            "USD" if e == "D" else EMPRESAS[e][0], contraparte=contra)

    ic("A", "2026-03", "venta_ic", "Venta a C", 240_000, "C")        # 30,000 USD
    ic("C", "2026-03", "compra_ic", "Compra a A", 29_000, "A")       # C dice 29,000
    ic("B", "2026-05", "venta_ic", "Venta a E", 400_000, "E")        # 20,000 USD
    ic("E", "2026-05", "compra_ic", "Compra a B", 160_000, "B")      # 20,000 USD, coincide
    ic("F", "2026-07", "venta_ic", "Venta a B", 5_000, "B")          # B no registra la compra

    df = pd.DataFrame(filas)[COLUMNAS]
    df["monto"] = df["monto"].astype(object)
    referencia = pd.DataFrame({"ingreso_mensual_usd": {e: v[1] for e, v in EMPRESAS.items()}})
    return df, referencia
