"""Orquesta las reglas, arma el semaforo por empresa y el registro de auditoria."""
import json
import datetime as dt
import pandas as pd

from . import config, reglas
from .modelos import Hallazgo, BLOQUEANTE, ADVERTENCIA, INFO


def controles_aplicables(df, referencia):
    """Para cada empresa, que controles obligatorios SI pudieron verificarse con los datos recibidos."""
    out = {}
    for e, g in df.groupby("empresa"):
        t = set(g["tipo"])
        out[e] = {
            "moneda": referencia is not None and e in referencia.index and "ingreso" in t,
            "balance": {"activo", "pasivo", "patrimonio"} <= t,
            "totales": "total" in t,
            "utilidad": "utilidad" in t,
            "razonabilidad": g.loc[g["tipo"] == "ingreso", "periodo"].nunique() >= 4,
        }
    return out


def validar(df_raw, referencia=None, tasas=None):
    tasas = tasas or config.TASAS
    hallazgos = []
    # tasa mal escrita / fuera de rango
    for m, (lo, hi) in config.RANGO_TASAS.items():
        if m in tasas and not (lo <= tasas[m] <= hi):
            hallazgos.append(Hallazgo("GRUPO", "tasas", None, m, "moneda.tasa_fuera_de_rango", BLOQUEANTE,
                                      f"La tasa {m}/USD = {tasas[m]} esta fuera del rango razonable",
                                      tasas[m], f"{lo} a {hi}", "Corregir la tabla de tasas"))
    hallazgos += reglas.estructura(df_raw)

    df = df_raw.copy()
    df["monto"] = pd.to_numeric(df["monto"], errors="coerce")
    df = df.dropna(subset=["monto"])               # lo no numerico ya se reporto arriba
    ctx = {"tasas": tasas, "referencia": referencia}

    for regla in reglas.REGLAS:
        if regla is reglas.razonabilidad:
            ctx["empresas_con_moneda_mal"] = {h.empresa for h in hallazgos
                                              if h.regla in ("moneda.equivocada", "moneda.tasa_no_definida")}
        hallazgos += regla(df, ctx)

    aplic = controles_aplicables(df, referencia)
    tasa_mal = any(h.regla == "moneda.tasa_fuera_de_rango" for h in hallazgos)
    semaforo = {}
    for e in sorted(df_raw["empresa"].unique()):
        hs = [h for h in hallazgos if h.empresa == e]
        bloq = sum(h.severidad == BLOQUEANTE for h in hs) + (1 if tasa_mal else 0)
        adv = sum(h.severidad == ADVERTENCIA for h in hs)
        sin_verificar = [c for c in config.CONTROLES_OBLIGATORIOS if not aplic.get(e, {}).get(c, False)]
        # fail-closed: lo que no se pudo verificar no cuenta como bueno
        estado = "ROJO" if bloq else "SIN_VERIFICAR" if sin_verificar else "AMARILLO" if adv else "VERDE"
        semaforo[e] = {"estado": estado, "bloqueantes": bloq, "advertencias": adv,
                       "controles_ejecutados": [c for c in config.CONTROLES_OBLIGATORIOS if c not in sin_verificar],
                       "sin_verificar": sin_verificar}
    return hallazgos, semaforo


def puerta(df_raw, semaforo, justificadas=()):
    """Solo pasan al consolidado las empresas sin bloqueantes. Las amarillas pasan si
    estan en 'justificadas' (alguien las aprobo)."""
    ok = [e for e, s in semaforo.items()
          if s["estado"] == "VERDE" or (s["estado"] == "AMARILLO" and e in justificadas)]
    return df_raw[df_raw["empresa"].isin(ok)].copy(), ok


def registrar_auditoria(ruta, usuario, accion, detalle):
    with open(ruta, "a", encoding="utf-8") as f:
        f.write(json.dumps({"cuando": dt.datetime.now().isoformat(timespec="seconds"),
                            "quien": usuario, "accion": accion, "detalle": detalle},
                           ensure_ascii=False) + "\n")


def reporte_texto(hallazgos, semaforo):
    icono = {"VERDE": "[VERDE]", "AMARILLO": "[AMARILLO]", "ROJO": "[ROJO]", "SIN_VERIFICAR": "[SIN VERIFICAR]"}
    sev = {BLOQUEANTE: "BLOQ", ADVERTENCIA: "ADV ", INFO: "INFO"}
    n_ok = sum(s["estado"] == "VERDE" for s in semaforo.values())
    n_bl = sum(s["estado"] == "ROJO" for s in semaforo.values())
    lineas = [f"{n_ok} empresas listas, {n_bl} bloqueadas, {len(semaforo) - n_ok - n_bl} con advertencias o sin verificar", ""]
    for h in [x for x in hallazgos if x.empresa == "GRUPO"]:
        lineas.append(f"[GRUPO] {h.mensaje}")
    for e, s in semaforo.items():
        extra = f", sin verificar: {', '.join(s['sin_verificar'])}" if s["sin_verificar"] else ""
        lineas.append(f"{icono[s['estado']]} Empresa {e}: {s['bloqueantes']} bloqueantes, {s['advertencias']} advertencias{extra}")
        for h in [x for x in hallazgos if x.empresa == e]:
            lineas.append(f"    {sev[h.severidad]} fila {h.fila} | {h.regla} | {h.mensaje}")
            lineas.append(f"         encontrado: {h.valor_encontrado} | esperado: {h.valor_esperado} | {h.sugerencia}")
    return "\n".join(lineas)
