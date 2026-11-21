"""Fase 3: reenvio entre ejecuciones (solo advierte)."""
import csv
import shutil
from pathlib import Path

import pytest

from conftest import DATA, KEY, ROOT
from nexus.audit import write_run
from nexus.historial import previous_runs
from nexus.pipeline import run

TOL = KEY["tolerancia_intercompania_usd"]


def ejecutar(data, salida, historial=True):
    r = run(data, ic_tolerance_usd=TOL, profiles_dir=ROOT / "profiles", history_dir=salida if historial else None)
    return r


def reglas(r, regla):
    return [f for f in r.findings if f.rule_id == regla]


def test_primera_ejecucion_y_sin_historial_no_advierten(tmp_path):
    r = ejecutar(DATA, tmp_path / "nada")
    assert reglas(r, "REE-01") == [] and reglas(r, "REE-02") == []


def test_dos_ejecuciones_sucesivas_del_mismo_archivo_advierten_con_la_fecha_previa(tmp_path):
    salida = tmp_path / "out"
    r1 = ejecutar(DATA, salida)
    write_run(r1, salida, source_dir=DATA)
    r2 = ejecutar(DATA, salida)
    f = reglas(r2, "REE-01")
    assert len(f) == 6 and {x.company_id for x in f} == set(r2.config.companies)         # uno por archivo de empresa
    anterior = previous_runs(salida)[0]
    assert all(r1.run_id in x.message and anterior["cuando"] in x.message for x in f)     # id y fecha de la ejecucion previa
    assert all(x.severity == "WARN" and "posible reenvio" in x.message.lower() for x in f)
    assert reglas(r2, "REE-02") == []                                                     # ya cubierto por el archivo


def test_solo_advierte_no_cambia_ninguna_cifra(tmp_path):
    salida = tmp_path / "out"
    r1 = ejecutar(DATA, salida)
    write_run(r1, salida, source_dir=DATA)
    r2 = ejecutar(DATA, salida)
    sin = ejecutar(DATA, salida, historial=False)
    for p in sin.periods:
        assert r2.periods[p].summary == sin.periods[p].summary
        assert r2.periods[p].provisional_reasons == sin.periods[p].provisional_reasons   # tampoco el estado
    assert {r.record_id: r.status for r in r2.records} == {r.record_id: r.status for r in sin.records}


def test_un_archivo_corregido_que_repite_ids_advierte_por_id(tmp_path):
    salida = tmp_path / "out"
    r1 = ejecutar(DATA, salida)
    write_run(r1, salida, source_dir=DATA)
    d2 = tmp_path / "data2"
    shutil.copytree(DATA, d2, ignore=shutil.ignore_patterns("generate.py", "README_SINTETICO.md"))
    f = d2 / "distribuidora_central_gt.csv"                                               # cambia el contenido (otro hash)
    f.write_text(f.read_text(encoding="utf-8").replace("Ventas netas;2.600.000,00", "Ventas netas;2.610.000,00", 1),
                 encoding="utf-8")
    r2 = ejecutar(d2, salida)
    ree1 = {x.company_id for x in reglas(r2, "REE-01")}
    assert "EMP002" not in ree1 and len(ree1) == 5                                        # los otros 5 siguen idénticos
    ree2 = reglas(r2, "REE-02")
    assert len(ree2) == 1 and ree2[0].company_id == "EMP002" and r1.run_id in ree2[0].message
    assert "aunque el archivo distribuidora_central_gt.csv cambio" in ree2[0].message


def test_usa_la_ejecucion_mas_reciente(tmp_path):
    salida = tmp_path / "out"
    r1 = ejecutar(DATA, salida)
    write_run(r1, salida, source_dir=DATA)
    (salida / r1.run_id).rename(salida / "run-20200101-000000")
    r1b = ejecutar(DATA, salida)
    write_run(r1b, salida, source_dir=DATA)
    cuando = [p["cuando"] for p in previous_runs(salida)]
    assert len(cuando) == 2 and cuando[1] == "2020-01-01 00:00:00" and cuando[0] > cuando[1]
    msg = reglas(ejecutar(DATA, salida), "REE-01")[0].message
    assert cuando[0] in msg and "2020-01-01" not in msg                                   # la mas reciente


def test_tiene_ficha_de_diagnostico(tmp_path):
    from nexus import diagnostico as DG
    salida = tmp_path / "out"
    r1 = ejecutar(DATA, salida)
    write_run(r1, salida, source_dir=DATA)
    fichas = [f for f in DG.diagnosticar(ejecutar(DATA, salida)) if f.tipo == DG.REENVIO]
    assert len(fichas) == 6 and all("probable" in f.causa_probable.lower() and f.donde for f in fichas)


def test_el_flujo_normal_no_depende_del_historial():
    assert reglas(run(DATA, ic_tolerance_usd=TOL), "REE-01") == []                        # history_dir=None por defecto
