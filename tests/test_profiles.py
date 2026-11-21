import csv
import dataclasses
import json
from pathlib import Path

import pytest

from conftest import DATA
from nexus.profiles import (ProfileError, apply_profiles, content_hash, from_dict, load_profiles,
                            save_profile, shared_source_conflicts, to_dict, validate_profile)
from nexus.text import norm


def test_hay_un_perfil_valido_por_empresa(built_profiles, cfg):
    profiles = load_profiles(built_profiles)
    assert set(profiles) == set(cfg.companies)
    for p in profiles.values():
        assert validate_profile(p, cfg) == [], p.company_id


def test_perfil_refleja_los_csv_del_grupo(built_profiles, cfg):
    profiles = load_profiles(built_profiles)
    with open(DATA / "equivalencias.csv", encoding="utf-8-sig", newline="") as f:
        eq = list(csv.DictReader(f))
    for p in profiles.values():
        exp = {r["cuenta_local"]: r["account_code"] for r in eq if r["company_id"] == p.company_id}
        assert p.accounts == exp
        assert p.counterparty_aliases == cfg.companies[p.company_id].aliases
        assert p.functional_currency == cfg.companies[p.company_id].currency
        assert p.source.file == cfg.companies[p.company_id].file


def test_formatos_y_monedas_distintas_en_los_perfiles(built_profiles):
    profiles = load_profiles(built_profiles)
    assert {p.source.type for p in profiles.values()} == {"xlsx", "csv", "json"}
    assert {p.currency_mode for p in profiles.values()} == {"column", "file_key"}


def test_aprobacion_y_version_quedan_registradas(built_profiles):
    for p in load_profiles(built_profiles).values():
        assert p.approved_by == "Tester" and p.approval_status == "APPROVED" and p.profile_version == 1
        assert p.profile_hash == content_hash(p)


def test_version_sube_solo_si_cambia_el_contenido(built_profiles, cfg):
    from nexus import ingestion
    from nexus.profiles import build_profile
    prof = load_profiles(built_profiles)["EMP001"]
    c = cfg.companies["EMP001"]
    tables = ingestion.READERS[".xlsx"](DATA / c.file)
    same = build_profile(c, tables, prof.accounts, "xlsx", existing=prof)
    assert same.profile_version == 1
    changed = build_profile(c, tables, {**prof.accounts, "Cuenta nueva": "6300"}, "xlsx", existing=prof)
    assert changed.profile_version == 2 and changed.profile_hash != prof.profile_hash


def test_perfil_editado_a_mano_se_detecta(built_profiles, cfg):
    path = built_profiles / "EMP001.json"
    d = json.loads(path.read_text(encoding="utf-8"))
    d["accounts"]["Ventas de varilla y alambre"] = "5000"
    path.write_text(json.dumps(d), encoding="utf-8")
    errs = validate_profile(load_profiles(built_profiles)["EMP001"], cfg)
    assert any("cambio sin actualizar" in e for e in errs)


@pytest.mark.parametrize("mutate,fragment", [
    (lambda d: d["accounts"].update({"Rara": "9999"}), "no existe en el catalogo"),
    (lambda d: d.update(currency_mode="inventado"), "Modo de moneda"),
    (lambda d: d["source"].update(type="pdf"), "Tipo de fuente"),
    (lambda d: d["columns"].pop("amount"), "Falta la columna"),
    (lambda d: d.update(functional_currency="EUR"), "sin tasas"),
    (lambda d: d.update(schema_version=99), "schema_version"),
])
def test_validacion_rechaza_perfiles_invalidos(built_profiles, cfg, mutate, fragment):
    d = to_dict(load_profiles(built_profiles)["EMP002"])
    mutate(d)
    d.pop("profile_hash")
    errs = validate_profile(from_dict(d), cfg)
    assert any(fragment in e for e in errs), errs


def test_dos_empresas_no_pueden_compartir_archivo(built_profiles):
    profiles = load_profiles(built_profiles)
    profiles["EMP002"].source.file = profiles["EMP001"].source.file
    assert shared_source_conflicts(profiles) == {profiles["EMP001"].source.file: ["EMP001", "EMP002"]}


def test_perfil_mal_formado_falla_claro():
    with pytest.raises(ProfileError):
        from_dict({"company_id": "X"})


def test_apply_profiles_crea_empresa_nueva_solo_con_perfil(built_profiles, cfg):
    import copy
    profiles = load_profiles(built_profiles)
    nueva = dataclasses.replace(profiles["EMP004"], company_id="EMP007", company_name="Ferrex Nueva",
                                counterparty_aliases=["Ferrex Nueva"])
    nueva.source = dataclasses.replace(nueva.source, file="nueva.xlsx")
    profiles["EMP007"] = nueva
    cfg2 = apply_profiles(copy.deepcopy(cfg), profiles)
    assert "EMP007" in cfg2.companies and cfg2.companies["EMP007"].file == "nueva.xlsx"
    some = next(iter(nueva.accounts))
    assert cfg2.equivalences[("EMP007", norm(some))] == nueva.accounts[some]
