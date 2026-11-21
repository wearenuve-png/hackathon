from decimal import ROUND_HALF_UP, Decimal

import pytest

from conftest import DATA, find
from nexus.consolidation import trace
from nexus.pipeline import run
from nexus.schemas import BLOCKED, EXCLUDED_DUPLICATE, PENDING_MAPPING


def q2(d):
    return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@pytest.fixture(scope="module")
def result(key):
    return run(DATA, ic_tolerance_usd=key["tolerancia_intercompania_usd"])


def test_consolidado_por_cuenta_igual_a_la_clave(result, key):
    for p, exp in key["consolidado_esperado_usd"].items():
        got = {c: str(q2(ln.amount_usd)) for c, ln in result.periods[p].lines.items()}
        assert got == exp["por_cuenta"], p


def test_resumen_igual_a_la_clave(result, key):
    for p, exp in key["consolidado_esperado_usd"].items():
        got = {k: str(q2(v)) for k, v in result.periods[p].summary.items()}
        assert got == exp["resumen"], p


def test_suma_ingenua_igual_a_la_clave(result, key):
    for p, exp in key["suma_ingenua_sin_eliminar_usd"].items():
        assert {k: str(q2(result.periods[p].naive_summary[k])) for k in exp} == exp


def test_eliminar_no_cambia_la_utilidad(result):
    for pr in result.periods.values():
        assert pr.summary["utilidad_neta"] == pr.naive_summary["utilidad_neta"]


def test_balance_cuadra(result):
    for pr in result.periods.values():
        assert q2(pr.summary["activo_menos_pasivo_y_patrimonio"]) == 0


def test_mes_incompleto_es_provisional(result, key):
    for p, exp in key["consolidado_esperado_usd"].items():
        pr = result.periods[p]
        assert pr.missing_companies == exp["empresas_faltantes"]
        if exp["incompleto"]:
            assert pr.provisional


def test_nada_se_excluye_en_silencio(result, key):
    """Cada registro que la clave deja fuera aparece en 'excluded' con motivo e importe."""
    expected_out = {"moneda_invalida": BLOCKED, "cuenta_sin_mapear": PENDING_MAPPING,
                    "signo_invertido": BLOCKED, "duplicado_confirmado": EXCLUDED_DUPLICATE}
    for e in key["errores_sembrados"]:
        if e["tipo"] not in expected_out:
            continue
        for loc in e["ubicaciones"]:
            r = find(result.records, loc)
            if r.status == "OK":          # la primera factura del duplicado si entra
                continue
            assert r.status == expected_out[e["tipo"]]
            item = next(x for x in result.periods[loc["period"]].excluded if x.record_id == r.record_id)
            assert item.reasons and item.amount_original == Decimal(loc["amount_local"])
    for pr in result.periods.values():
        assert len(pr.excluded) == sum(1 for r in result.records if r.period == pr.period
                                       and r.status not in ("OK", "TOTAL"))


def test_duplicado_excluido_con_ajuste_reversible(result):
    dups = [a for a in result.adjustments if a.kind == "DUPLICATE_EXCLUSION"]
    assert dups and all(a.reversible and a.reason and a.rule for a in dups)
    ids = {r.record_id for r in result.records}
    assert all(rid in ids for a in dups for rid in a.record_ids)   # el original no se borra


def test_trazabilidad_de_una_cifra(result):
    for p in result.periods:
        for code in result.periods[p].lines:
            t = trace(p, code, result)
            total = sum((x["amount_usd"] for x in t["records"]), Decimal(0)) + \
                sum((a["amount_usd"] for a in t["adjustments"]), Decimal(0))
            assert total == t["amount_usd"]
            for x in t["records"]:
                assert x["file"] and x["row"] and x["amount_usd"] == x["amount_original"] * x["fx_rate"]
