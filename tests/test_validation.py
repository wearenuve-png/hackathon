import csv
from decimal import Decimal

import pytest

from conftest import DATA, find
from nexus.pipeline import run

RULE = {"moneda_invalida": "MON-01", "total_no_cuadra": "TOT-01", "duplicado_confirmado": "DUP-01",
        "posible_duplicado": "DUP-02", "cuenta_sin_mapear": "MAP-01", "diferencia_intercompania": "IC-01",
        "importe_atipico": "ATI-01", "signo_invertido": "SIGN-01", "mes_faltante": "MES-01"}


@pytest.fixture(scope="module")
def res(key):
    return run(DATA, ic_tolerance_usd=key["tolerancia_intercompania_usd"])


def _ids(res, err):
    return {find(res.records, loc).record_id for loc in err["ubicaciones"] if "row" in loc}


def _err(key, tipo):
    return next(e for e in key["errores_sembrados"] if e["tipo"] == tipo)


def test_detecta_cada_error_sembrado(res, key):
    for err in key["errores_sembrados"]:
        hits = [f for f in res.findings if f.rule_id == RULE[err["tipo"]]]
        assert hits, f"No se detecto {err['tipo']}"
        if err["tipo"] == "mes_faltante":
            loc = err["ubicaciones"][0]
            assert any(f.company_id == loc["company_id"] and f.period == loc["period"] for f in hits)
        else:
            covered = set().union(*(set(f.record_ids) for f in hits))
            assert _ids(res, err) <= covered, err["tipo"]


def test_sin_falsos_positivos(res, key):
    """Todo hallazgo corresponde a un error sembrado: ninguna alarma sobre datos limpios."""
    seeded = set()
    for err in key["errores_sembrados"]:
        seeded |= _ids(res, err)
    missing = _err(key, "mes_faltante")["ubicaciones"][0]
    for f in res.findings:
        assert f.rule_id in RULE.values(), f.rule_id
        if f.rule_id == "MES-01":
            assert (f.company_id, f.period) == (missing["company_id"], missing["period"])
        else:
            assert set(f.record_ids) & seeded, f"Falso positivo: {f.rule_id} {f.message}"


def test_total_diferencia_igual_a_la_clave(res, key):
    f = next(f for f in res.findings if f.rule_id == "TOT-01")
    declared = Decimal(find(res.records, _err(key, "total_no_cuadra")["ubicaciones"][0]).amount_original)
    assert Decimal(f.found.replace(",", "")) == declared
    assert Decimal(f.found.replace(",", "")) - Decimal(f.expected.replace(",", "")) == Decimal("5000")


def test_posible_duplicado_solo_se_marca(res, key):
    for loc in _err(key, "posible_duplicado")["ubicaciones"]:
        r = find(res.records, loc)
        assert r.status == "OK" and "POSSIBLE_DUPLICATE" in r.flags and r.adjustment_ids == []


def test_error_7_muestra_impacto_sin_modificar_la_cifra(res, key):
    loc = _err(key, "importe_atipico")["ubicaciones"][0]
    with open(DATA / "tasas.csv", encoding="utf-8") as fh:
        rate = next(Decimal(r["usd_por_unidad_local"]) for r in csv.DictReader(fh)
                    if r["periodo"] == loc["period"] and r["moneda"] == "GTQ")
    amt = Decimal(loc["amount_local"])
    f = next(f for f in res.findings if f.rule_id == "ATI-01")
    assert f"{amt * rate:,.2f}" in f.impact and f"{amt:,.2f}" in f.impact and "NO modificada" in f.impact
    r = find(res.records, loc)
    assert r.amount_usd == amt and r.status == "OK" and "ATYPICAL" in r.flags     # cifra intacta
    assert res.periods[loc["period"]].provisional


def test_rango_de_impacto_del_signo_invertido(res, key):
    loc = _err(key, "signo_invertido")["ubicaciones"][0]
    r = find(res.records, loc)
    mag = abs(r.amount_usd)
    pr = res.periods[loc["period"]]
    i = next(i for i in pr.impact_ranges if i.record_id == r.record_id)
    assert i.utility_excluded == 0
    assert i.utility_as_is == mag and i.utility_corrected == -mag     # es un gasto
    assert (i.utility_low, i.utility_high) == (-mag, mag)
    assert pr.provisional and pr.utility_range[0] < pr.summary["utilidad_neta"] < pr.utility_range[1]


def test_moneda_invalida_no_se_adivina_en_el_impacto(res, key):
    loc = _err(key, "moneda_invalida")["ubicaciones"][0]
    r = find(res.records, loc)
    i = next(i for i in res.periods[loc["period"]].impact_ranges if i.record_id == r.record_id)
    assert i.utility_as_is is None and "Hipotesis" in i.note and r.amount_usd is None


def test_mes_faltante_marca_periodo_incompleto(res, key):
    loc = _err(key, "mes_faltante")["ubicaciones"][0]
    pr = res.periods[loc["period"]]
    assert loc["company_id"] in pr.missing_companies and pr.provisional
