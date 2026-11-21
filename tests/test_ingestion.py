from decimal import Decimal

from conftest import find
from nexus.schemas import PENDING_MAPPING, TOTAL


def test_lee_todos_los_registros(records, key):
    assert len(records) == sum(key["conteo_registros_por_estado"].values())


def test_cada_registro_conserva_su_origen(records):
    for r in records:
        assert r.source_file and r.source_row and r.raw


def test_ubicaciones_de_la_clave_coinciden(records, key):
    for err in key["errores_sembrados"]:
        for loc in err["ubicaciones"]:
            if "row" not in loc:
                continue
            r = find(records, loc)
            assert r.company_id == loc["company_id"]
            assert r.period == loc["period"]
            assert r.account_local == loc["account_local"]
            assert r.amount_original == Decimal(loc["amount_local"])


def test_cuenta_sin_mapear_queda_pendiente(records, key):
    err = next(e for e in key["errores_sembrados"] if e["tipo"] == "cuenta_sin_mapear")
    for loc in err["ubicaciones"]:
        r = find(records, loc)
        assert r.status == PENDING_MAPPING and r.account_code is None


def test_conteo_de_pendientes_y_totales(records, key):
    cnt = key["conteo_registros_por_estado"]
    assert sum(r.status == PENDING_MAPPING for r in records) == cnt.get("pending_mapping", 0)
    assert sum(r.status == TOTAL for r in records) == cnt.get("total", 0)


def test_moneda_explicita_no_se_corrige(records, key):
    """La moneda escrita se conserva tal cual (no se infiere ni se corrige al leer)."""
    for e in key["errores_sembrados"]:
        for loc in e["ubicaciones"]:
            if "row" in loc:
                assert find(records, loc).currency == loc["currency_written"]


def test_contrapartes_del_grupo_por_alias(records, key):
    ic_refs = {e["reference"] for e in key["eliminaciones_esperadas"] + key["discrepancias_esperadas"]}
    ic = [r for r in records if r.transaction_id in ic_refs]
    assert ic and all(r.counterparty_id is not None for r in ic)
