"""Reglas de validacion.

apply_record_rules: las reglas que CAMBIAN el estado de un registro y por eso corren antes de
consolidar (duplicado confirmado por ID, signo invertido). El resto del validador (totales,
posibles duplicados, importes atipicos, meses faltantes) se agrega en la fase SHOULD.
"""
from collections import defaultdict
from typing import List, Tuple

from .schemas import (BLOCK, BLOCKED, EXCLUDED_DUPLICATE, INFO, OK, Adjustment, Finding, GroupConfig,
                      Record)

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


def apply_record_rules(records: List[Record], cfg: GroupConfig) -> Tuple[List[Adjustment], List[Finding]]:
    adj, f1 = confirmed_duplicates(records, cfg)
    f2 = inverted_signs(records, cfg)
    return adj, f1 + f2


def reverse_adjustment(adj: Adjustment, records: List[Record]) -> None:
    """Revierte un ajuste de exclusion: el registro original vuelve a OK (nunca se borro)."""
    if not adj.reversible:
        raise ValueError("Ajuste no reversible")
    for r in records:
        if r.record_id in adj.record_ids and r.status == EXCLUDED_DUPLICATE:
            r.status = OK
            r.adjustment_ids.remove(adj.adjustment_id)
            r.status_reasons.append(f"Ajuste {adj.adjustment_id} revertido")


def validate(records: List[Record], cfg: GroupConfig) -> List[Finding]:
    """Fase SHOULD (validador completo): pendiente."""
    return []
