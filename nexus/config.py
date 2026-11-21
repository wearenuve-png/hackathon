"""Carga la configuracion del grupo desde archivos CSV con nombres fijos (contrato del motor):

    empresas.csv          company_id, nombre, pais, moneda_funcional, archivo, alias (separados por |)
    tasas.csv             periodo, moneda, usd_por_unidad_local   (o local_por_usd)
    catalogo_cuentas.csv  account_code, account_name, estado, clase, corriente, total_de
    equivalencias.csv     company_id, cuenta_local, account_code
    periodos.csv          periodo, tipo
"""
import csv
from decimal import Decimal
from pathlib import Path

from .schemas import Account, Company, FxRate, GroupConfig, LOCAL_PER_USD, USD_PER_LOCAL
from .text import norm


def _rows(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_group_config(config_dir, ic_tolerance_usd="1.00") -> GroupConfig:
    d = Path(config_dir)
    companies = {}
    for r in _rows(d / "empresas.csv"):
        aliases = [a.strip() for a in (r.get("alias") or "").split("|") if a.strip()]
        companies[r["company_id"]] = Company(r["company_id"], r["nombre"], r.get("pais", ""),
                                             r["moneda_funcional"].strip().upper(), r["archivo"], aliases)
    rates = {}
    for r in _rows(d / "tasas.csv"):
        cur = r["moneda"].strip().upper()
        if r.get("usd_por_unidad_local"):
            fx = FxRate(r["periodo"], cur, Decimal(r["usd_por_unidad_local"]), USD_PER_LOCAL)
        else:
            fx = FxRate(r["periodo"], cur, Decimal(r["local_por_usd"]), LOCAL_PER_USD)
        rates[(fx.period, cur)] = fx
    catalog = {}
    for r in _rows(d / "catalogo_cuentas.csv"):
        corr = (r.get("corriente") or "").strip().upper()
        catalog[r["account_code"]] = Account(
            r["account_code"], r["account_name"], r["estado"], r["clase"],
            {"S": True, "N": False}.get(corr),
            [c for c in (r.get("total_de") or "").split("|") if c],
            (r.get("naturaleza") or "").strip().upper() or None)
    equivalences = {(r["company_id"], norm(r["cuenta_local"])): r["account_code"]
                    for r in _rows(d / "equivalencias.csv")}
    periods = {r["periodo"]: r["tipo"] for r in _rows(d / "periodos.csv")}
    return GroupConfig(companies, rates, catalog, equivalences, periods,
                       ic_tolerance_usd=Decimal(ic_tolerance_usd))
