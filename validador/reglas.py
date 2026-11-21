"""Reglas de validacion. Todas son deterministas y genericas (no atadas a los datos de prueba).

Cada regla: f(df, ctx) -> list[Hallazgo]
df  = partidas normalizadas con monto numerico (ver modelos.py)
ctx = dict con 'tasas' y 'referencia' (DataFrame empresa -> ingreso_mensual_usd)
"""
import re
import pandas as pd

from . import config
from .modelos import Hallazgo, BLOQUEANTE, ADVERTENCIA, INFO, TIPOS

PERIODO_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _f(v):
    return f"{v:,.2f}"


def _filas(sub):
    return sorted(int(x) for x in sub["fila"].tolist())


def _archivo(df, empresa):
    s = df.loc[df["empresa"] == empresa, "archivo"]
    return s.iloc[0] if len(s) else ""


def moneda_de(df, empresa):
    s = df.loc[df["empresa"] == empresa, "moneda"].dropna()
    return s.mode().iloc[0] if len(s) else "USD"


# ---------------------------------------------------------------- estructura
def estructura(df_raw, ctx=None):
    """Se corre sobre el df CRUDO (antes de convertir monto a numero)."""
    out = []
    for _, r in df_raw.iterrows():
        e, a, fila = r["empresa"], r["archivo"], r["fila"]
        if pd.isna(pd.to_numeric(r["monto"], errors="coerce")):
            vacio = pd.isna(r["monto"]) or str(r["monto"]).strip() == ""
            out.append(Hallazgo(e, a, fila, "monto", "estructura.monto_no_numerico", BLOQUEANTE,
                                "Celda de monto vacia" if vacio else "Texto donde deberia haber un numero",
                                None if vacio else r["monto"], "numero",
                                "Completar o corregir el monto en el archivo de origen"))
        if not PERIODO_RE.match(str(r["periodo"])):
            out.append(Hallazgo(e, a, fila, "periodo", "estructura.fecha_invalida", BLOQUEANTE,
                                "Fecha/periodo con formato invalido", r["periodo"], "YYYY-MM",
                                "Escribir el periodo como AAAA-MM"))
        if r["tipo"] not in TIPOS:
            out.append(Hallazgo(e, a, fila, "tipo", "estructura.tipo_desconocido", ADVERTENCIA,
                                "Tipo de partida no reconocido", r["tipo"], sorted(TIPOS),
                                "Mapear la cuenta a un tipo conocido"))
    return out


# ---------------------------------------------------------------- integridad
def duplicados(df, ctx=None):
    out = []
    clave = ["empresa", "periodo", "concepto", "tipo", "monto", "contraparte"]
    d = df.copy()
    d["contraparte"] = d["contraparte"].fillna("")
    dup = d[d.duplicated(subset=clave, keep=False)]
    for k, g in dup.groupby(clave):
        e = k[0]
        out.append(Hallazgo(e, _archivo(df, e), _filas(g), "fila", "integridad.duplicado", BLOQUEANTE,
                            f"Partida duplicada '{k[2]}' de {k[1]} ({len(g)} veces)",
                            _f(k[4]), "una sola fila", "Eliminar la fila repetida"))
    return out


def meses_faltantes(df, ctx=None):
    out = []
    esperados = sorted(set(df["periodo"]))
    for e, g in df.groupby("empresa"):
        faltan = [p for p in esperados if p not in set(g["periodo"])]
        if faltan:
            out.append(Hallazgo(e, _archivo(df, e), None, "periodo", "integridad.mes_faltante", BLOQUEANTE,
                                f"Faltan {len(faltan)} mes(es) del presupuesto", ", ".join(faltan),
                                f"{len(esperados)} meses", "Agregar los meses faltantes"))
    return out


def signos(df, ctx=None):
    out = []
    pos = df[df["tipo"].isin(["ingreso", "costo", "gasto", "activo", "venta_ic", "compra_ic"]) & (df["monto"] < 0)]
    for (e, p), g in pos.groupby(["empresa", "periodo"]):
        out.append(Hallazgo(e, _archivo(df, e), _filas(g), "monto", "integridad.signo_invertido", BLOQUEANTE,
                            f"Monto negativo en partida que debe ser positiva ({p})",
                            _f(g["monto"].sum()), "positivo",
                            "Revisar el signo: probablemente capturado al reves"))
    return out


def totales(df, ctx=None):
    out = []
    tot = df[df["tipo"] == "total"]
    for _, t in tot.iterrows():
        sub = df[(df["empresa"] == t["empresa"]) & (df["periodo"] == t["periodo"])
                 & (df["grupo"] == t["grupo"]) & (df["tipo"] != "total")]
        if sub.empty:
            continue
        suma = sub["monto"].sum()
        dif = t["monto"] - suma
        if abs(dif) > config.TOLERANCIA_REL * max(abs(suma), 1):
            out.append(Hallazgo(t["empresa"], t["archivo"], int(t["fila"]), "monto", "integridad.total_descuadrado",
                                BLOQUEANTE,
                                f"El total de '{t['grupo']}' en {t['periodo']} no cuadra con sus partidas "
                                f"(diferencia {_f(dif)})",
                                _f(t["monto"]), _f(suma),
                                "Corregir el total o la partida que lo desajusta"))
    return out


# ---------------------------------------------------------------- contable
def balance(df, ctx=None):
    out = []
    for (e, p), g in df.groupby(["empresa", "periodo"]):
        a = g.loc[g["tipo"] == "activo", "monto"].sum()
        pa = g.loc[g["tipo"] == "pasivo", "monto"].sum()
        pt = g.loc[g["tipo"] == "patrimonio", "monto"].sum()
        if not ((g["tipo"] == "activo").any() and (g["tipo"] == "pasivo").any()):
            continue
        dif = a - (pa + pt)
        if abs(dif) > config.TOLERANCIA_REL * max(abs(a), 1):
            out.append(Hallazgo(e, _archivo(df, e), _filas(g[g["tipo"].isin(["activo", "pasivo", "patrimonio"])]),
                                "monto", "contable.balance_descuadrado", BLOQUEANTE,
                                f"Activo != Pasivo + Patrimonio en {p} (diferencia {_f(dif)})",
                                f"Activo {_f(a)}", f"Pasivo+Patrimonio {_f(pa + pt)}",
                                "Revisar las partidas del balance"))
    return out


def utilidad(df, ctx=None):
    out = []
    for (e, p), g in df.groupby(["empresa", "periodo"]):
        rep = g[g["tipo"] == "utilidad"]
        if rep.empty:
            continue
        esperado = (g.loc[g["tipo"] == "ingreso", "monto"].sum()
                    - g.loc[g["tipo"] == "costo", "monto"].sum()
                    - g.loc[g["tipo"] == "gasto", "monto"].sum())
        v = rep["monto"].sum()
        if abs(v - esperado) > config.TOLERANCIA_REL * max(abs(esperado), 1):
            out.append(Hallazgo(e, _archivo(df, e), _filas(rep), "monto", "contable.utilidad_descuadrada",
                                BLOQUEANTE,
                                f"Utilidad != Ingresos - Costos - Gastos en {p}",
                                _f(v), _f(esperado), "Recalcular la utilidad"))
    return out


# ---------------------------------------------------------------- moneda
def moneda(df, ctx):
    out = []
    tasas, ref = ctx["tasas"], ctx.get("referencia")
    for e, g in df.groupby("empresa"):
        declaradas = set(g["moneda"].dropna())
        if len(declaradas) > 1:
            out.append(Hallazgo(e, _archivo(df, e), None, "moneda", "moneda.mezclada", ADVERTENCIA,
                                "El archivo mezcla varias monedas", ", ".join(sorted(declaradas)),
                                "una sola moneda", "Unificar la moneda del archivo"))
        decl = moneda_de(df, e)
        if decl not in tasas:
            out.append(Hallazgo(e, _archivo(df, e), None, "moneda", "moneda.tasa_no_definida", BLOQUEANTE,
                                f"No hay tasa de cambio definida para {decl}", decl,
                                ", ".join(tasas), "Agregar la tasa en la tabla de tasas"))
            continue
        if ref is None or e not in ref.index:
            continue
        ing = g[g["tipo"] == "ingreso"].groupby("periodo")["monto"].sum()
        if ing.empty:
            continue
        razon = ing.median() / ref.loc[e, "ingreso_mensual_usd"]
        mejor = min(tasas, key=lambda m: abs(razon / tasas[m] - 1))
        if abs(razon / tasas[mejor] - 1) <= config.TOLERANCIA_TASA and mejor != decl:
            out.append(Hallazgo(e, _archivo(df, e), None, "moneda", "moneda.equivocada", BLOQUEANTE,
                                f"Parece {mejor} marcado como {decl}: los ingresos son {razon:.1f} veces "
                                f"el historial, que coincide con la tasa {mejor}/USD ({tasas[mejor]:g})",
                                f"{_f(ing.median())} {decl}/mes", f"~{_f(ref.loc[e, 'ingreso_mensual_usd'] * tasas[decl])} {decl}/mes",
                                f"Cambiar la moneda declarada a {mejor} o reexportar el archivo"))
    return out


# ---------------------------------------------------------------- entre empresas
def intercompania(df, ctx):
    out = []
    tasas = ctx["tasas"]
    ic = df[df["tipo"].isin(["venta_ic", "compra_ic"])].copy()
    if ic.empty:
        return out
    ic["usd"] = ic.apply(lambda r: r["monto"] / tasas.get(moneda_de(df, r["empresa"]), 1.0), axis=1)
    ventas = ic[ic["tipo"] == "venta_ic"].groupby(["empresa", "contraparte", "periodo"])
    compras = ic[ic["tipo"] == "compra_ic"].groupby(["contraparte", "empresa", "periodo"])
    v = ventas["usd"].sum().rename("venta")
    c = compras["usd"].sum().rename("compra")
    c.index.names = ["empresa", "contraparte", "periodo"]  # (vendedor, comprador, periodo)
    tabla = pd.concat([v, c], axis=1).fillna(0.0).reset_index()
    for _, r in tabla.iterrows():
        vend, comp, p, dv, dc = r["empresa"], r["contraparte"], r["periodo"], r["venta"], r["compra"]
        sub = ic[(ic["periodo"] == p) & (((ic["empresa"] == vend) & (ic["contraparte"] == comp) & (ic["tipo"] == "venta_ic"))
                                         | ((ic["empresa"] == comp) & (ic["contraparte"] == vend) & (ic["tipo"] == "compra_ic")))]
        filas = [f"{x.empresa}:{int(x.fila)}" for x in sub.itertuples()]  # filas de ambas empresas
        base = max(dv, dc)
        if dv == 0 or dc == 0:
            quien = vend if dc == 0 else comp
            falta = "la compra" if dc == 0 else "la venta"
            out.append(Hallazgo(quien, _archivo(df, quien), filas, "monto", "intercompania.sin_contraparte",
                                BLOQUEANTE, f"{vend} reporta venta a {comp} en {p} pero {comp} no registra {falta}"
                                if dc == 0 else f"{comp} reporta compra a {vend} en {p} pero {vend} no registra la venta",
                                f"{_f(dv)} USD vendido / {_f(dc)} USD comprado", "montos iguales",
                                "Registrar la operacion en la empresa que falta"))
        elif abs(dv - dc) > config.TOLERANCIA_REL * base:
            rel = abs(dv - dc) / base
            out.append(Hallazgo(vend, _archivo(df, vend), filas, "monto", "intercompania.diferencia",
                                ADVERTENCIA if rel <= 0.05 else BLOQUEANTE,
                                f"{vend} dice vender {_f(dv)} USD a {comp} en {p}, pero {comp} dice comprar {_f(dc)} USD "
                                f"(diferencia {_f(abs(dv - dc))} USD, {rel:.1%})",
                                f"{_f(dv)} vs {_f(dc)}", "montos iguales",
                                "Conciliar con la otra empresa antes de eliminar en la consolidacion"))
    return out


# ---------------------------------------------------------------- razonabilidad
def razonabilidad(df, ctx):
    """Un mes cuyo ingreso se aleja mucho de la mediana de la propia empresa."""
    out = []
    saltar = ctx.get("empresas_con_moneda_mal", set())
    for e, g in df[df["tipo"] == "ingreso"].groupby("empresa"):
        if e in saltar:
            continue
        mensual = g.groupby("periodo")["monto"].sum()
        if len(mensual) < 4:
            continue
        med = mensual.median()
        if med <= 0:
            continue
        for p, v in mensual.items():
            r = v / med
            if r > config.FACTOR_RAZONABILIDAD or r < 1 / config.FACTOR_RAZONABILIDAD:
                filas = _filas(g[g["periodo"] == p])
                out.append(Hallazgo(e, _archivo(df, e), filas, "monto", "razonabilidad.variacion_atipica",
                                    ADVERTENCIA,
                                    f"Los ingresos de {p} son {r:.1f} veces la mediana de la empresa",
                                    _f(v), f"~{_f(med)}", "Confirmar el dato o justificar la variacion"))
    return out


REGLAS = [duplicados, meses_faltantes, signos, totales, balance, utilidad, moneda, intercompania, razonabilidad]
