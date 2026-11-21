from collections import defaultdict
from decimal import Decimal

import pytest

from nexus.currency import convert
from nexus.intercompany import eliminations, match
from nexus.schemas import FLAG_IC_DISCREPANCY

TIPO = {"operacion": "ER", "saldo": "BG"}


@pytest.fixture()
def ic(records, cfg):
    convert(records, cfg)
    m = match(records, cfg)
    return records, m, eliminations(m, records)


def _key(e):
    return (e["period"], e["reference"], TIPO[e["tipo"]], e["seller"], e["buyer"])


def test_conciliadas_igual_a_la_clave(ic, key):
    _, matches, _ = ic
    got = {(m.period, m.reference, m.statement, m.seller_id, m.buyer_id): m.seller_usd
           for m in matches if m.status == "RECONCILED"}
    exp = {_key(e): Decimal(e["eliminated_usd"]) for e in key["eliminaciones_esperadas"]}
    assert got == exp


def test_discrepancias_igual_a_la_clave(ic, key):
    _, matches, _ = ic
    got = {(m.period, m.reference, m.statement, m.seller_id, m.buyer_id): m.difference_usd
           for m in matches if m.status == "DISCREPANCY"}
    exp = {_key(e): Decimal(e["difference_usd"]) for e in key["discrepancias_esperadas"]}
    assert got == exp


def test_no_hay_operaciones_sin_pareja(ic):
    _, matches, _ = ic
    assert [m for m in matches if m.status == "UNMATCHED"] == []


def test_solo_se_elimina_lo_conciliado(ic, key):
    records, matches, adj = ic
    by_match = defaultdict(Decimal)
    rid_to_match = {rid: m for m in matches for rid in m.seller_record_ids + m.buyer_record_ids}
    for a in adj:
        m = rid_to_match[a.record_ids[0]]
        assert m.status == "RECONCILED"
        by_match[m.match_id] += a.amount_usd
    for m in matches:
        if m.status == "RECONCILED":
            assert by_match[m.match_id] == -(m.seller_usd + m.buyer_usd)


def test_discrepancia_queda_marcada_y_sin_ajuste(ic):
    records, matches, _ = ic
    disc_ids = {rid for m in matches if m.status == "DISCREPANCY" for rid in m.seller_record_ids + m.buyer_record_ids}
    assert disc_ids
    for r in records:
        if r.record_id in disc_ids:
            assert FLAG_IC_DISCREPANCY in r.flags and r.adjustment_ids == []


def test_control_del_brief_utilidad_no_cambia():
    """A vende 30 a C: ingresos 250->220, costos 130->100, utilidad 120 igual (ejemplo del brief)."""
    from nexus.schemas import Account, Company, FxRate, GroupConfig, Record
    cat = {"4000": Account("4000", "Ingresos", "ER", "ingreso"), "5000": Account("5000", "Costo", "ER", "costo")}
    comps = {c: Company(c, c, "", "USD", "", []) for c in ("A", "C")}
    cfg = GroupConfig(comps, {("P", "USD"): FxRate("P", "USD", Decimal(1))}, cat, {}, {"P": "real"})

    def rec(i, cid, code, amt, cp=None):
        return Record(i, cid, "f", None, 1, {}, period="P", account_code=code, amount_original=Decimal(amt),
                      currency="USD", counterparty_id=cp, transaction_id="T1" if cp else None)
    rs = [rec("1", "A", "4000", 70), rec("2", "A", "4000", 30, "C"), rec("3", "A", "5000", 40),
          rec("4", "C", "4000", 150), rec("5", "C", "5000", 60), rec("6", "C", "5000", 30, "A")]
    convert(rs, cfg)
    adj = eliminations(match(rs, cfg), rs)
    elim = {c: sum(a.amount_usd for a in adj if a.account_code == c) for c in ("4000", "5000")}
    ing = sum(r.amount_usd for r in rs if r.account_code == "4000") + elim["4000"]
    cos = sum(r.amount_usd for r in rs if r.account_code == "5000") + elim["5000"]
    assert (ing, cos, ing - cos) == (Decimal(220), Decimal(100), Decimal(120))
