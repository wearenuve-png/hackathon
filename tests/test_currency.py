import csv
from decimal import Decimal

from conftest import DATA, find
from nexus.currency import convert, to_usd, to_usd_divide, to_usd_multiply
from nexus.schemas import BLOCKED, LOCAL_PER_USD, USD_PER_LOCAL, FxRate


def test_control_multiplica():
    assert to_usd_multiply(Decimal("80000"), Decimal("0.125")) == Decimal("10000")


def test_control_divide_caso_inverso():
    assert to_usd_divide(Decimal("80000"), Decimal("8")) == Decimal("10000")


def test_ambas_orientaciones_dan_lo_mismo():
    a = to_usd(Decimal("77000"), FxRate("2026-10", "GTQ", Decimal("0.125"), USD_PER_LOCAL))
    b = to_usd(Decimal("77000"), FxRate("2026-10", "GTQ", Decimal("8"), LOCAL_PER_USD))
    assert a == b == Decimal("9625")


def test_cada_registro_es_reproducible(records, cfg):
    """importe_usd == importe_original x tasa del mes leida de tasas.csv, sin redondeo."""
    with open(DATA / "tasas.csv", encoding="utf-8") as f:
        rates = {(r["periodo"], r["moneda"]): Decimal(r["usd_por_unidad_local"]) for r in csv.DictReader(f)}
    convert(records, cfg)
    converted = [r for r in records if r.amount_usd is not None]
    assert converted
    for r in converted:
        assert r.fx_rate == rates[(r.period, r.currency)]
        assert r.amount_usd == r.amount_original * rates[(r.period, r.currency)]


def test_moneda_invalida_se_bloquea(records, cfg, key):
    convert(records, cfg)
    err = next(e for e in key["errores_sembrados"] if e["tipo"] == "moneda_invalida")
    for loc in err["ubicaciones"]:
        r = find(records, loc)
        assert r.status == BLOCKED and r.amount_usd is None
        assert any("Moneda" in m for m in r.status_reasons)


def test_eliminaciones_de_la_clave_coinciden_en_usd(records, cfg, key):
    """Los importes USD de las filas intercompania de la clave salen igual al convertir."""
    convert(records, cfg)
    for e in key["eliminaciones_esperadas"] + key["discrepancias_esperadas"]:
        tot = {"seller": Decimal(0), "buyer": Decimal(0)}
        for side, cid in (("seller", e["seller"]), ("buyer", e["buyer"])):
            for r in records:
                if r.company_id == cid and r.source_row in e[f"{side}_rows"] and r.transaction_id == e["reference"]:
                    tot[side] += r.amount_usd
        assert tot["seller"] == Decimal(e["seller_usd"])
        assert tot["buyer"] == Decimal(e["buyer_usd"])
