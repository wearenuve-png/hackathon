"""Reglas de validacion.

apply_record_rules: las reglas que CAMBIAN el estado de un registro y por eso corren antes de
consolidar (duplicado confirmado por ID, signo invertido). El resto del validador (totales,
posibles duplicados, importes atipicos, meses faltantes) se agrega en la fase SHOULD.
"""
from collections import defaultdict
from decimal import Decimal
from statistics import median
from typing import List, Tuple

from .consolidation import UTILITY_SIGN
from .currency import known_currencies, to_usd
from .schemas import (BLOCK, BLOCKED, EXCLUDED_DUPLICATE, FLAG_ATYPICAL, FLAG_POSSIBLE_DUPLICATE, INFO, OK,
                      PENDING_MAPPING, TOTAL, WARN, Adjustment, Finding, GroupConfig, Record)

ATYPICAL_RATIO = Decimal("3")          # variacion generica contra otros periodos de la misma cuenta
CURRENCY_FIT_TOLERANCE = Decimal("0.15")
CURRENCY_TRIGGER = Decimal("1.5")      # solo se plantea hipotesis de moneda si la cifra se aleja >50%
TOTAL_TOLERANCE = Decimal("0.01")

# Clases de cuenta de flujo que, por convencion del catalogo, se registran en positivo.
POSITIVE_FLOW_CLASSES = {"ingreso", "costo", "gasto_operativo", "gasto_financiero", "impuesto"}


def _fid(prefix, n):
    return f"{prefix}-{n:04d}"


def confirmed_duplicates(records: List[Record], cfg: GroupConfig):
    """Mismo ID de transaccion + misma empresa, periodo, cuenta e importe = duplicado confirmado.
    Se conserva la primera fila; las demas se excluyen con un ajuste registrado y reversible."""
    groups = defaultdict(list)
    for r in records:
        if r.status == OK and r.transaction_id:
            groups[(r.company_id, r.transaction_id, r.period, r.account_code, r.amount_original)].append(r)
    adjustments, findings = [], []
    for (cid, tx, period, code, amt), rs in groups.items():
        if len(rs) < 2:
            continue
        rs = sorted(rs, key=lambda r: (r.source_sheet or "", r.source_row))
        keep, dups = rs[0], rs[1:]
        for d in dups:
            a = Adjustment(_fid("ADJ-DUP", len(adjustments) + 1), "DUPLICATE_EXCLUSION", [d.record_id],
                           -(d.amount_usd or 0), code, period,
                           f"Duplicado confirmado de {keep.record_id} (mismo ID {tx})",
                           "DUP-01: mismo ID de transaccion, empresa, periodo, cuenta e importe")
            d.status = EXCLUDED_DUPLICATE
            d.status_reasons.append(f"Duplicado confirmado: ID {tx} ya registrado en fila {keep.source_row}")
            d.adjustment_ids.append(a.adjustment_id)
            adjustments.append(a)
        findings.append(Finding(_fid("F-DUP", len(findings) + 1), "DUP-01", INFO,
                                f"Factura {tx} aparece {len(rs)} veces en {cid}; se excluyen {len(dups)} "
                                f"mediante ajuste reversible", [r.record_id for r in rs], period, cid,
                                found=f"{len(rs)} filas", expected="1 fila",
                                suggestion="Confirmar con la empresa y corregir el archivo de origen"))
    return adjustments, findings


def inverted_signs(records: List[Record], cfg: GroupConfig):
    findings = []
    for r in records:
        acc = cfg.catalog.get(r.account_code or "")
        if r.status == OK and acc and acc.cls in POSITIVE_FLOW_CLASSES and r.amount_original is not None \
                and r.amount_original < 0:
            r.block(BLOCKED, f"Signo invertido: {acc.name} debe ser positivo y viene {r.amount_original}")
            findings.append(Finding(_fid("F-SIGN", len(findings) + 1), "SIGN-01", BLOCK,
                                    f"Signo invertido en {r.account_local} ({r.company_id}, {r.period})",
                                    [r.record_id], r.period, r.company_id, str(r.amount_original), "positivo",
                                    "Corregir el signo en el archivo de origen y volver a cargar"))
    return findings


def out_of_period(records: List[Record], cfg: GroupConfig):
    """Fecha valida pero fuera del calendario del grupo (periodos.csv): se bloquea, nunca se reubica."""
    if not cfg.periods:
        return []
    out = []
    for r in records:
        if r.status != TOTAL and r.period and r.period not in cfg.periods:
            reason = f"Periodo {r.period} fuera del calendario del grupo ({', '.join(sorted(cfg.periods))})"
            if r.status == OK:
                r.block(BLOCKED, reason)
            else:
                r.status_reasons.insert(0, reason)          # el motivo del calendario va primero
            out.append(Finding(_fid("F-FEC", len(out) + 1), "FEC-01", BLOCK,
                               f"Registro de {r.company_id} con periodo {r.period}, fuera del calendario del grupo",
                               [r.record_id], r.period, r.company_id, r.period, ", ".join(sorted(cfg.periods)),
                               "Corregir la fecha en el archivo de origen o ampliar el calendario"))
    return out


def apply_record_rules(records: List[Record], cfg: GroupConfig) -> Tuple[List[Adjustment], List[Finding]]:
    f0 = out_of_period(records, cfg)
    adj, f1 = confirmed_duplicates(records, cfg)
    f2 = inverted_signs(records, cfg)
    return adj, f0 + f1 + f2


def reverse_adjustment(adj: Adjustment, records: List[Record]) -> None:
    """Revierte un ajuste de exclusion: el registro original vuelve a OK (nunca se borro)."""
    if not adj.reversible:
        raise ValueError("Ajuste no reversible")
    for r in records:
        if r.record_id in adj.record_ids and r.status == EXCLUDED_DUPLICATE:
            r.status = OK
            r.adjustment_ids.remove(adj.adjustment_id)
            r.status_reasons.append(f"Ajuste {adj.adjustment_id} revertido")


def _f(n, prefix):
    return f"{prefix}-{n:04d}"


def _m(d):
    return f"{d:,.2f}"


def totals(records, cfg):
    """Recalcula cada total y lo compara con la suma de sus partidas (en moneda original)."""
    out = []
    for t in (r for r in records if r.status == TOTAL and r.amount_original is not None):
        parts_codes = set(cfg.catalog[t.account_code].total_of)
        parts = [r for r in records if r.company_id == t.company_id and r.period == t.period
                 and r.account_code in parts_codes and r.status == OK and r.amount_original is not None]
        if not parts:
            continue
        calc = sum((r.amount_original for r in parts), Decimal(0))
        diff = t.amount_original - calc
        if abs(diff) > TOTAL_TOLERANCE:
            rate = t.fx_rate
            usd = f" (~{_m(diff * rate)} USD)" if rate else ""
            out.append(Finding(_f(len(out) + 1, "F-TOT"), "TOT-01", BLOCK,
                               f"Total '{t.account_local}' de {t.company_id} en {t.period} no cuadra con sus partidas: "
                               f"declarado {_m(t.amount_original)}, recalculado {_m(calc)}, diferencia {_m(diff)} "
                               f"{t.currency}{usd}. El total no se acepta; el consolidado usa las partidas.",
                               [t.record_id] + [r.record_id for r in parts], t.period, t.company_id,
                               _m(t.amount_original), _m(calc), "Corregir el total o la partida que lo desajusta"))
    return out


def possible_duplicates(records, cfg):
    """Mismo importe, fecha y contraparte, sin ID de transaccion: solo se marca."""
    groups = defaultdict(list)
    for r in records:
        if r.status == OK and not r.transaction_id and r.date and r.counterparty_text \
                and r.amount_original is not None:
            groups[(r.company_id, r.date, r.account_code, r.amount_original, r.counterparty_text.lower())].append(r)
    out = []
    for (cid, d, code, amt, cp), rs in groups.items():
        if len(rs) < 2:
            continue
        for r in rs:
            r.flags.append(FLAG_POSSIBLE_DUPLICATE)
        out.append(Finding(_f(len(out) + 1, "F-PDUP"), "DUP-02", WARN,
                           f"Posible duplicado en {cid}: {len(rs)} registros con el mismo importe ({_m(amt)}), "
                           f"fecha ({d}) y contraparte ({rs[0].counterparty_text}), sin ID de transaccion. "
                           f"Ambos siguen en el consolidado hasta confirmar.",
                           [r.record_id for r in rs], rs[0].period, cid, f"{len(rs)} registros", "1 registro",
                           "Confirmar con la empresa si es una sola operacion",
                           impact=f"Si fuera duplicado, el gasto bajaria {_m(amt * rs[0].fx_rate)} USD"
                           if rs[0].fx_rate else None))
    return out


def _agg(records):
    """(empresa, cuenta, periodo) -> (registros OK, suma USD, suma original, moneda dominante)."""
    g = defaultdict(list)
    for r in records:
        if r.status == OK and r.amount_usd is not None and r.account_code:
            g[(r.company_id, r.account_code, r.period)].append(r)
    out = {}
    for k, rs in g.items():
        dom = max(rs, key=lambda r: abs(r.amount_original)).currency
        out[k] = (rs, sum((r.amount_usd for r in rs), Decimal(0)), sum((r.amount_original for r in rs), Decimal(0)), dom)
    return out


def atypical_amounts(records, cfg):
    """Cuenta agregada que se aleja de sus otros periodos. Si otra moneda la explica, lo dice.
    Una anomalia significa 'revisar': no modifica ninguna cifra."""
    agg = _agg(records)
    cur_all = known_currencies(cfg)
    out = []
    for (cid, code, p), (rs, usd, orig, dom) in sorted(agg.items()):
        # referencia robusta: mediana de TODOS los periodos de la cuenta (con 2 periodos no se puede
        # saber cual es el atipico, asi que se exigen al menos 3)
        series = [v[1] for (c2, a2, p2), v in agg.items() if c2 == cid and a2 == code]
        if len(series) < 3 or cfg.catalog[code].cls == "patrimonio":
            continue
        ref = Decimal(str(median(series)))
        if ref <= 0 or usd <= 0:
            continue
        ratio = usd / ref
        if CURRENCY_TRIGGER ** -1 <= ratio <= CURRENCY_TRIGGER:
            continue
        func = cfg.companies[cid].currency
        hypothesis = None
        for x in sorted(cur_all - {dom}):
            rate = cfg.rates.get((p, x))
            if rate is None:
                continue
            fit = to_usd(orig, rate)
            if abs(fit / ref - 1) <= CURRENCY_FIT_TOLERANCE:
                hypothesis = (x, rate, fit)
                if x == func:
                    break
        if hypothesis:
            x, rate, fit = hypothesis
            sign = UTILITY_SIGN.get(cfg.catalog[code].cls)
            efecto = (f"Efecto en utilidad si fuera {x}: {sign * (fit - usd):+,.2f} USD." if sign
                      else "La cuenta es de balance: no afecta la utilidad.")
            impact = (f"Si fuera {x}: {_m(orig)} x {rate.rate} = {_m(fit)} USD, frente a {_m(usd)} USD "
                      f"en el consolidado (diferencia {_m(usd - fit)} USD). Cifra NO modificada. "
                      f"Como {x}: {_m(fit)} USD | como {dom}: {_m(usd)} USD. {efecto}")
            msg = (f"Posible error de moneda en {cid}, {rs[0].account_local} ({p}): el importe esta marcado como "
                   f"{dom}; {_m(usd)} USD es {ratio:.1f} veces su nivel habitual ({_m(ref)} USD) y {x} lo "
                   f"explica. No se corrige automaticamente.")
            sev, sug = WARN, f"Confirmar con la empresa si el importe esta en {x}"
        elif ratio > ATYPICAL_RATIO or ratio < 1 / ATYPICAL_RATIO:
            impact = f"Variacion de {_m(usd - ref)} USD frente a su nivel habitual. Cifra NO modificada."
            msg = (f"Importe atipico en {cid}, cuenta {code} ({p}): {_m(usd)} USD, {ratio:.1f} veces su nivel "
                   f"habitual ({_m(ref)} USD).")
            sev, sug = WARN, "Revisar o justificar la variacion"
        else:
            continue
        for r in rs:
            r.flags.append(FLAG_ATYPICAL)
        out.append(Finding(_f(len(out) + 1, "F-ATI"), "ATI-01", sev, msg, [r.record_id for r in rs], p, cid,
                           f"{_m(usd)} USD", f"~{_m(ref)} USD", sug, impact=impact))
    return out


def missing_months(records, cfg):
    out = []
    have = defaultdict(set)
    for r in records:
        if r.period:
            have[r.company_id].add(r.period)
    for cid in sorted(cfg.companies):
        for p in sorted(cfg.periods):
            if p not in have[cid]:
                out.append(Finding(_f(len(out) + 1, "F-MES"), "MES-01", WARN,
                                   f"{cid} no trae datos de {p}. El consolidado de ese mes no incluye a la empresa "
                                   f"y queda incompleto.", [], p, cid, "sin registros", "registros del mes",
                                   "Pedir el archivo del mes faltante a la empresa"))
    return out


def unresolved_records(records, cfg):
    """Un hallazgo por registro bloqueado o pendiente (el motivo ya esta en el registro)."""
    out = []
    for r in records:
        if r.status == PENDING_MAPPING:
            out.append(Finding(_f(len(out) + 1, "F-MAP"), "MAP-01", WARN,
                               f"Cuenta sin equivalencia en {r.company_id}: {r.account_local!r}. No entra al "
                               f"consolidado hasta confirmar el mapeo.", [r.record_id], r.period, r.company_id,
                               r.account_local, "cuenta del catalogo", "Mapear la cuenta al catalogo comun"))
        elif r.status == BLOCKED and not any("Signo invertido" in m for m in r.status_reasons):
            moneda = any("Moneda" in m or "tasa" in m.lower() for m in r.status_reasons)
            out.append(Finding(_f(len(out) + 1, "F-BLQ"), "MON-01" if moneda else "ING-01", BLOCK,
                               f"Registro bloqueado en {r.company_id}, {r.account_local} ({r.period}): "
                               + "; ".join(r.status_reasons), [r.record_id], r.period, r.company_id,
                               r.currency if moneda else None, "codigo de moneda valido" if moneda else None,
                               "Corregir el dato en el archivo de origen y volver a cargar"))
    return out


def unbalanced(records, cfg):
    """Activo != Pasivo + Patrimonio por empresa y periodo (en USD), si la empresa reporto las tres clases."""
    g = defaultdict(lambda: defaultdict(Decimal))
    ids = defaultdict(list)
    for r in records:
        if r.status == OK and r.amount_usd is not None and r.account_code:
            cls = cfg.catalog[r.account_code].cls
            if cls in ("activo", "pasivo", "patrimonio"):
                g[(r.company_id, r.period)][cls] += r.amount_usd
                ids[(r.company_id, r.period)].append(r.record_id)
    out = []
    for (cid, p), c in sorted(g.items()):
        if set(c) != {"activo", "pasivo", "patrimonio"}:
            continue
        diff = c["activo"] - c["pasivo"] - c["patrimonio"]
        if abs(diff) > TOTAL_TOLERANCE:
            out.append(Finding(_f(len(out) + 1, "F-BAL"), "BAL-01", WARN,
                               f"Balance descuadrado en {cid} ({p}): activo {_m(c['activo'])} USD, pasivo + patrimonio "
                               f"{_m(c['pasivo'] + c['patrimonio'])} USD, diferencia {_m(diff)} USD.",
                               ids[(cid, p)], p, cid, _m(c["activo"]), _m(c["pasivo"] + c["patrimonio"]),
                               "Revisar las partidas del balance de la empresa"))
    return out


def cross_file_duplicates(records, cfg):
    """Mismo ID de transaccion (y mismo importe) en archivos de empresas DISTINTAS, sin que sea una operacion
    intercompania (sin contraparte): posible doble registro. Solo advierte."""
    g = defaultdict(list)
    for r in records:
        if r.status == OK and r.transaction_id and not r.counterparty_id and r.amount_usd is not None:
            g[(r.transaction_id, r.period, r.account_code, r.amount_usd)].append(r)
    out = []
    for (tx, p, code, usd), rs in sorted(g.items(), key=lambda kv: kv[0][0]):
        if len({r.company_id for r in rs}) < 2:
            continue
        for r in rs:
            if FLAG_POSSIBLE_DUPLICATE not in r.flags:
                r.flags.append(FLAG_POSSIBLE_DUPLICATE)
        out.append(Finding(_f(len(out) + 1, "F-XDUP"), "DUP-03", WARN,
                           f"El ID {tx} aparece en archivos de empresas distintas ({', '.join(sorted({r.company_id for r in rs}))}) "
                           f"con el mismo importe ({_m(usd)} USD) y sin ser una operacion intercompania. Ambos siguen "
                           f"en el consolidado hasta confirmar.", [r.record_id for r in rs], p, rs[0].company_id,
                           f"{len(rs)} archivos", "1 archivo", "Confirmar con las empresas cual es el registro valido"))
    return out


def validate(records: List[Record], cfg: GroupConfig) -> List[Finding]:
    return (totals(records, cfg) + possible_duplicates(records, cfg) + cross_file_duplicates(records, cfg)
            + atypical_amounts(records, cfg) + missing_months(records, cfg) + unbalanced(records, cfg)
            + unresolved_records(records, cfg))


def validate_indicator_inputs(params, ebit, invested_capital, capital_employed, period=None):
    """Comprueba las entradas de ROIC/ROCE/EVA (capital positivo, tasas razonables). Un error de entrada
    bloquea el indicador: no pasa inadvertido. La logica vive en metrics.validate_inputs."""
    from .metrics import validate_inputs
    return validate_inputs(params, ebit, invested_capital, capital_employed, period)
