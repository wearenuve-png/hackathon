import copy
from decimal import Decimal

import pytest

from nexus.adapters import adapter_for
from nexus.accounts import nature
from nexus.profiles import apply_profiles
from nexus.schemas import BLOCKED, OK, PENDING_MAPPING, CompanyProfile, SourceSpec

D = Decimal
CSV = """Periodo,Cuenta,Debe,Haber,Moneda
2026-10,Ventas,,"1,000.00",GTQ
2026-10,Sueldos,400.00,,GTQ
2026-10,Caja,250.00,,GTQ
2026-10,Proveedores,,100.00,GTQ
2026-10,Sueldos,,50.00,GTQ
2026-10,Ventas,10.00,20.00,GTQ
2026-10,Sueldos,,,GTQ
2026-10,Cuenta rara,70.00,,GTQ
2026-10,Sueldos,abc,,GTQ
"""
ACCOUNTS = {"Ventas": "4000", "Sueldos": "6000", "Caja": "1000", "Proveedores": "2000"}


@pytest.fixture()
def setup(cfg, tmp_path):
    f = tmp_path / "dc.csv"
    f.write_text(CSV, encoding="utf-8")
    prof = CompanyProfile("EMP900", "Empresa DC", "GT", "GTQ", SourceSpec("csv", "dc.csv"),
                          {"period": "Periodo", "account": "Cuenta", "debit": "Debe", "credit": "Haber",
                           "currency": "Moneda"}, ACCOUNTS, sign_convention="debit_credit",
                          currency_mode="column", currency_key="Moneda", counterparty_aliases=[])
    cfg2 = apply_profiles(copy.deepcopy(cfg), {"EMP900": prof})
    return cfg2, f, prof


def test_naturaleza_por_clase_y_sobrescritura(cfg):
    assert nature("1000", cfg) == "D" and nature("5000", cfg) == "D" and nature("6000", cfg) == "D"
    assert nature("2000", cfg) == "C" and nature("3000", cfg) == "C" and nature("4000", cfg) == "C"
    assert nature("TOT_ING", cfg) == "C"          # el total hereda la de sus componentes
    cfg.catalog["4000"].nature = "D"
    assert nature("4000", cfg) == "D"
    cfg.catalog["4000"].nature = None


def _ingest(setup, use_profile):
    cfg2, f, prof = setup
    recs, _ = adapter_for("csv").ingest(f, "EMP900", cfg2, prof if use_profile else None)
    return recs


@pytest.mark.parametrize("use_profile", [True, False])
def test_signo_natural_por_cuenta(setup, use_profile):
    r = _ingest(setup, use_profile)
    assert (r[0].amount_original, r[0].status) == (D("1000.00"), OK)      # ingreso en haber: positivo
    assert (r[1].amount_original, r[1].status) == (D("400.00"), OK)       # gasto en debe: positivo
    assert r[2].amount_original == D("250.00")                            # activo en debe: positivo
    assert r[3].amount_original == D("100.00")                            # pasivo en haber: positivo
    assert r[4].amount_original == D("-50.00")                            # gasto en haber: reversa, negativo


@pytest.mark.parametrize("use_profile", [True, False])
def test_filas_dudosas_no_se_asumen(setup, use_profile):
    r = _ingest(setup, use_profile)
    assert r[5].status == BLOCKED and "misma fila" in r[5].status_reasons[0]      # debito Y credito
    assert r[6].status == BLOCKED and "Ni debito ni credito" in r[6].status_reasons[0]
    assert r[7].status == PENDING_MAPPING and r[7].amount_original == D("70.00")   # naturaleza desconocida
    assert r[8].status == BLOCKED and "no numerico" in r[8].status_reasons[0]


def test_debito_y_credito_originales_se_conservan(setup):
    r = _ingest(setup, True)
    assert (r[1].debit, r[1].credit) == (D("400.00"), None) and (r[3].debit, r[3].credit) == (None, D("100.00"))
    assert r[0].raw["Haber"] == "1,000.00"


def test_el_modelo_canonico_y_el_motor_no_cambian(setup):
    """Despues de normalizar, un registro de debito/credito es igual a uno de monto con signo."""
    r = _ingest(setup, True)[1]
    assert r.amount_original is not None and r.account_code == "6000" and r.currency == "GTQ"
