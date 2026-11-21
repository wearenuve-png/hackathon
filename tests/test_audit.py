import csv
import hashlib
import json

from conftest import DATA
from nexus.audit import file_hashes, write_run
from nexus.pipeline import run


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_hashes_sha256_coinciden_con_el_calculo_independiente(key):
    res = run(DATA, ic_tolerance_usd=key["tolerancia_intercompania_usd"])
    assert res.input_hashes
    for name, h in res.input_hashes.items():
        assert len(h) == 64 and h == sha(DATA / name)
    for c in res.config.companies.values():
        assert c.file in res.input_hashes                      # cada archivo de empresa queda registrado


def test_file_hashes_distingue_contenido(tmp_path):
    a, b = tmp_path / "a.txt", tmp_path / "b.txt"
    a.write_text("uno"), b.write_text("dos")
    h = file_hashes([a, b])
    assert h["a.txt"] != h["b.txt"] and h["a.txt"] == hashlib.sha256(b"uno").hexdigest()


def test_write_run_exporta_evidencia_completa(tmp_path, key, built_profiles):
    res = run(DATA, ic_tolerance_usd=key["tolerancia_intercompania_usd"], profiles_dir=built_profiles)
    d = write_run(res, tmp_path)
    run_json = json.loads((open(d + "/run.json", encoding="utf-8")).read())
    assert run_json["run_id"] == res.run_id and run_json["rules_version"] == res.config.rules_version
    assert run_json["input_hashes"] == res.input_hashes
    assert set(run_json["periods"]) == set(key["consolidado_esperado_usd"])
    for p, exp in key["consolidado_esperado_usd"].items():                    # el export trae las cifras de la clave
        assert f"{float(run_json['periods'][p]['summary']['ingresos']):.2f}" == f"{float(exp['resumen']['ingresos']):.2f}"
    assert run_json["periods"]["2026-11"]["provisional"] is True
    assert set(run_json["load_reports"]) == set(res.config.companies)
    assert all(r["status"] == "MATCHED" for r in run_json["load_reports"].values())
    assert run_json["matches"] and run_json["adjustments"] and run_json["findings"]
    with open(d + "/records.csv", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == len(res.records)
    assert {r["record_id"] for r in rows} == {r.record_id for r in res.records}
    assert all(r["source_file"] and r["source_row"] for r in rows)


def test_ejecutar_no_modifica_los_archivos_fuente(tmp_path, key):
    before = {p.name: sha(p) for p in DATA.iterdir() if p.is_file()}
    write_run(run(DATA, ic_tolerance_usd=key["tolerancia_intercompania_usd"]), tmp_path)
    assert {p.name: sha(p) for p in DATA.iterdir() if p.is_file()} == before
