"""Pruebas de aceptacion de la arquitectura multiempresa (docs/NEXUS_Arquitectura_Multiempresa...):
el motor no cambia cuando cambia una fuente; lo particular de cada empresa vive en su perfil."""
import csv
import shutil
from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import load_workbook

from conftest import DATA, find
from nexus import ingestion
from nexus.pipeline import run
from nexus.profiles import build_profile, load_profiles, save_profile
from nexus.schemas import BLOCKED, OK, PENDING_MAPPING, Company

D = Decimal


def snapshot(res):
    return {r.record_id: (r.status, r.amount_original, r.amount_usd, r.account_code, r.currency)
            for r in res.records}


def rate(period, currency):
    with open(DATA / "tasas.csv", encoding="utf-8") as f:
        return next(D(r["usd_por_unidad_local"]) for r in csv.DictReader(f)
                    if r["periodo"] == period and r["moneda"] == currency)


@pytest.fixture()
def env(built_profiles, data_copy):
    base = run(data_copy, profiles_dir=built_profiles)
    return base, data_copy, built_profiles


# ------------------------------------------------------------------ 1. renombrar columnas
def test_renombrar_columnas_sin_tocar_el_motor(env):
    base, data, profs = env
    f = data / "aceros_ferrex_gt.xlsx"
    wb = load_workbook(f)
    ws = wb["Presupuesto"]
    ren = {"Monto": "Importe Total", "Cuenta": "Cuenta Contable"}
    for c in ws[1]:
        c.value = ren.get(c.value, c.value)
    wb.save(f)

    # sin actualizar el perfil: la fuente ya no coincide -> revision, nada se procesa en silencio
    rota = run(data, profiles_dir=profs)
    assert rota.load_reports["EMP001"].status == "REVIEW"
    assert not [r for r in rota.records if r.company_id == "EMP001"]

    # solo el perfil cambia (nueva version): mismo resultado que antes
    p = load_profiles(profs)["EMP001"]
    p.columns["amount"], p.columns["account"] = "Importe Total", "Cuenta Contable"
    p.profile_version += 1
    save_profile(p, profs)
    despues = run(data, profiles_dir=profs)
    assert despues.load_reports["EMP001"].status == "MATCHED"
    assert despues.load_reports["EMP001"].profile_version == 2
    assert snapshot(despues) == snapshot(base)
    for per in base.periods:
        assert despues.periods[per].summary == base.periods[per].summary


# ------------------------------------------------------------------ 2. cuarta empresa solo con perfil
NUEVA = """Periodo,Cuenta,Debe,Haber,Moneda
2026-10,Ventas netas,,"800,000.00",GTQ
2026-10,Costo de ventas,"500,000.00",,GTQ
2026-10,Sueldos,"100,000.00",,GTQ
2026-10,Caja,"150,000.00",,GTQ
2026-10,Proveedores,,"50,000.00",GTQ
2026-10,Capital,,"100,000.00",GTQ
"""
NUEVA_CUENTAS = {"Ventas netas": "4000", "Costo de ventas": "5000", "Sueldos": "6000", "Caja": "1000",
                 "Proveedores": "2000", "Capital": "3000"}


def test_agregar_una_empresa_nueva_solo_con_un_perfil(env):
    base, data, profs = env
    f = data / "ferrex_nicaragua.csv"
    f.write_text(NUEVA, encoding="utf-8")
    comp = Company("EMP007", "Ferrex Nicaragua", "Nicaragua", "GTQ", f.name, ["Ferrex Nicaragua"])
    tables = ingestion.READERS[".csv"](f)                      # onboarding: se detecta y se guarda el perfil
    prof = build_profile(comp, tables, NUEVA_CUENTAS, "csv", approved_by="Tester")
    assert prof.sign_convention == "debit_credit"
    save_profile(prof, profs)

    res = run(data, profiles_dir=profs)                         # ni una linea de codigo cambia
    assert res.load_reports["EMP007"].status == "MATCHED"
    assert len([r for r in res.records if r.company_id == "EMP007"]) == 6
    k = rate("2026-10", "GTQ")
    b, n = base.periods["2026-10"].summary, res.periods["2026-10"].summary
    assert n["ingresos"] - b["ingresos"] == D("800000") * k
    assert n["costo_ventas"] - b["costo_ventas"] == D("500000") * k
    assert n["gastos_operativos"] - b["gastos_operativos"] == D("100000") * k
    assert n["utilidad_neta"] - b["utilidad_neta"] == (D("800000") - D("500000") - D("100000")) * k
    assert n["activo_total"] - b["activo_total"] == D("150000") * k
    assert n["pasivo_total"] - b["pasivo_total"] == D("50000") * k
    assert n["activo_menos_pasivo_y_patrimonio"] == b["activo_menos_pasivo_y_patrimonio"] == 0
    # los demas meses quedan marcados: la empresa nueva no trae datos
    assert "EMP007" in res.periods["2026-11"].missing_companies and res.periods["2026-11"].provisional
    # y lo que ya existia no se altero
    assert {k_: v for k_, v in snapshot(res).items() if not k_.startswith("EMP007")} == snapshot(base)


# ------------------------------------------------------------------ 3. moneda desconocida bloquea
@pytest.mark.parametrize("valor,motivo", [("XYZ", "invalida"), ("", "faltante")])
def test_moneda_desconocida_o_vacia_bloquea(env, valor, motivo):
    base, data, profs = env
    f = data / "distribuidora_central_gt.csv"
    lines = f.read_text(encoding="utf-8").splitlines()
    i = next(n for n, ln in enumerate(lines) if n > 0 and ln.startswith("10/2026;Ventas netas;") and ";GTQ;" in ln)
    cols = lines[i].split(";")
    cols[3] = valor
    lines[i] = ";".join(cols)
    f.write_text("\n".join(lines) + "\n", encoding="utf-8")
    res = run(data, profiles_dir=profs)
    r = next(r for r in res.records if r.company_id == "EMP002" and r.source_row == i + 1)
    assert r.status == BLOCKED and r.amount_usd is None and motivo in r.status_reasons[0].lower()
    assert any(f.rule_id == "MON-01" and r.record_id in f.record_ids for f in res.findings)
    assert any(x.record_id == r.record_id for x in res.periods["2026-10"].excluded)
    assert res.periods["2026-10"].provisional
    assert res.periods["2026-10"].summary["ingresos"] < base.periods["2026-10"].summary["ingresos"]


# ------------------------------------------------------------------ 4. cuentas sin equivalencia -> revision
def test_cuenta_sin_equivalencia_va_a_revision_y_se_aprueba_en_el_perfil(env):
    base, data, profs = env
    f = data / "aceros_ferrex_gt.xlsx"
    wb = load_workbook(f)
    ws = wb["Presupuesto"]
    fila = next(r[0].row for r in ws.iter_rows(min_row=2) if r[1].value == "Fletes" and r[0].value == "2026-10")
    ws.cell(row=fila, column=2).value = "Fletes y acarreos"
    wb.save(f)

    res = run(data, profiles_dir=profs)
    r = next(r for r in res.records if r.company_id == "EMP001" and r.source_row == fila)
    assert r.status == PENDING_MAPPING and r.account_code is None and r.amount_usd is not None
    assert any(f.rule_id == "MAP-01" and r.record_id in f.record_ids for f in res.findings)
    assert res.periods["2026-10"].provisional
    assert res.periods["2026-10"].summary["gastos_operativos"] < base.periods["2026-10"].summary["gastos_operativos"]

    # una persona aprueba la equivalencia en el perfil (nueva version) y vuelve a cargar
    p = load_profiles(profs)["EMP001"]
    p.accounts["Fletes y acarreos"] = "6200"
    p.profile_version += 1
    save_profile(p, profs)
    ok = run(data, profiles_dir=profs)
    assert next(x for x in ok.records if x.record_id == r.record_id).status == OK
    assert ok.periods["2026-10"].summary == base.periods["2026-10"].summary


# ------------------------------------------------------------------ 5. fuentes distintas no se mezclan
def test_cada_registro_viene_del_archivo_de_su_perfil(env):
    base, data, profs = env
    profiles = load_profiles(profs)
    for r in base.records:
        assert r.source_file == profiles[r.company_id].source.file
        assert r.record_id.startswith(r.company_id + "|")


def test_equivalencias_son_por_empresa(env):
    base, data, profs = env
    p = load_profiles(profs)["EMP001"]
    p.accounts["Ventas netas"] = "4100"             # EMP002 llama "Ventas netas" a su cuenta 4000
    p.profile_version += 1
    save_profile(p, profs)
    res = run(data, profiles_dir=profs)
    assert snapshot(res) == snapshot(base)
    assert {r.account_code for r in res.records if r.company_id == "EMP002" and r.account_local == "Ventas netas"} \
        == {"4000"}


def test_archivo_de_otra_empresa_bajo_un_perfil_ajeno_no_se_procesa(env):
    base, data, profs = env
    shutil.copy(data / "transportes_ferrex_hn.csv", data / "distribuidora_central_gt.csv")   # ambos CSV
    res = run(data, profiles_dir=profs)
    assert res.load_reports["EMP002"].status == "REVIEW"
    assert not [r for r in res.records if r.company_id == "EMP002"]
    assert {r.source_file for r in res.records if r.company_id == "EMP005"} == {"transportes_ferrex_hn.csv"}


def test_dos_empresas_con_el_mismo_archivo_quedan_en_revision(env):
    base, data, profs = env
    p = load_profiles(profs)["EMP002"]
    p.source.file = "aceros_ferrex_gt.xlsx"
    p.profile_version += 1
    save_profile(p, profs)
    res = run(data, profiles_dir=profs)
    assert res.load_reports["EMP001"].status == "REVIEW" and res.load_reports["EMP002"].status == "REVIEW"
    assert any("varias empresas" in x for x in res.load_reports["EMP001"].reasons)
