"""Conciliacion intercompania. Solo se elimina lo conciliado.

Candidatos: registros en estado OK, convertidos a USD, con contraparte que es empresa del grupo.
Emparejamiento: (periodo, par de empresas, estado financiero, referencia). Si un lado no trae la
referencia, segundo intento por (periodo, par, estado financiero) con lo que quedo suelto.
  - ER: vendedor = lado con cuentas de ingreso; comprador = costo/gasto.
  - BG: vendedor = lado con cuentas de activo (CxC); comprador = pasivo (CxP).
Dentro de la tolerancia -> RECONCILED y se elimina cada registro por su propio importe.
Fuera de tolerancia -> DISCREPANCY abierta; no se elimina nada. Un solo lado -> UNMATCHED.
"""
from collections import defaultdict
from decimal import Decimal
from typing import List

from .schemas import (FLAG_IC_DISCREPANCY, FLAG_IC_UNMATCHED, OK, Adjustment, GroupConfig, ICMatch,
                      Record)

SELLER_CLASSES = {"ER": {"ingreso"}, "BG": {"activo"}}


def _candidates(records, cfg):
    return [r for r in records if r.status == OK and r.counterparty_id and r.amount_usd is not None
            and r.account_code in cfg.catalog]


def _build(key, recs, cfg, n):
    period, pair, statement, ref = key
    sides = defaultdict(list)
    for r in recs:
        sides[r.company_id].append(r)
    a, b = sorted(pair)
    seller = None
    for cid in (a, b):
        if sides[cid] and all(cfg.catalog[r.account_code].cls in SELLER_CLASSES[statement] for r in sides[cid]):
            seller = cid
    buyer = b if seller == a else a
    if seller is None:
        seller, buyer = a, b
    s_usd = sum((r.amount_usd for r in sides[seller]), Decimal(0))
    b_usd = sum((r.amount_usd for r in sides[buyer]), Decimal(0))
    if not sides[seller] or not sides[buyer]:
        status = "UNMATCHED"
    elif abs(s_usd - b_usd) <= cfg.ic_tolerance_usd:
        status = "RECONCILED"
    else:
        status = "DISCREPANCY"
    m = ICMatch(f"IC-{n:04d}", period, statement, seller, buyer, ref,
                [r.record_id for r in sides[seller]], [r.record_id for r in sides[buyer]], s_usd, b_usd, status)
    flag = {"DISCREPANCY": FLAG_IC_DISCREPANCY, "UNMATCHED": FLAG_IC_UNMATCHED}.get(status)
    for r in recs:
        r.ic_match_id = m.match_id
        if flag and flag not in r.flags:
            r.flags.append(flag)
    return m


def match(records: List[Record], cfg: GroupConfig) -> List[ICMatch]:
    cands = _candidates(records, cfg)
    groups = defaultdict(list)
    for r in cands:
        stmt = cfg.catalog[r.account_code].statement
        groups[(r.period, frozenset({r.company_id, r.counterparty_id}), stmt, r.transaction_id)].append(r)

    complete, loose = {}, defaultdict(list)
    for k, recs in groups.items():
        if len({r.company_id for r in recs}) == 2:
            complete[k] = recs
        else:
            loose[(k[0], k[1], k[2], None)].extend(recs)      # segundo intento sin referencia
    for k, recs in loose.items():
        complete[k] = recs

    out = []
    for n, k in enumerate(sorted(complete, key=lambda k: (k[0], sorted(k[1]), k[2], k[3] or "")), start=1):
        out.append(_build(k, complete[k], cfg, n))
    return out


def eliminations(matches: List[ICMatch], records: List[Record]) -> List[Adjustment]:
    by_id = {r.record_id: r for r in records}
    adj = []
    for m in matches:
        if m.status != "RECONCILED":
            continue
        for rid in m.seller_record_ids + m.buyer_record_ids:
            r = by_id[rid]
            a = Adjustment(f"ADJ-{m.match_id}-{len(adj) + 1:04d}", "IC_ELIMINATION", [rid], -r.amount_usd,
                           r.account_code, r.period,
                           f"Eliminacion intercompania {m.seller_id}->{m.buyer_id} ref {m.reference or 's/ref'} "
                           f"(conciliado: {m.seller_usd} vs {m.buyer_usd} USD)",
                           "IC-ELIM-01: solo se elimina lo conciliado dentro de tolerancia")
            r.adjustment_ids.append(a.adjustment_id)
            adj.append(a)
    return adj
