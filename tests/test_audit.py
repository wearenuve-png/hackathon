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


# ---------------------------------------------------------------- modo local: solo lectura y hash estable
def test_verify_hashes_detecta_ok_cambio_y_falta(tmp_path):
    from nexus.audit import verify_hashes
    a, b = tmp_path / "a.txt", tmp_path / "b.txt"
    a.write_text("uno"), b.write_text("dos")
    reg = file_hashes([a, b]) | {"c.txt": "0" * 64}
    b.write_text("dos modificado")
    v = verify_hashes(reg, [tmp_path])
    assert (v["a.txt"]["status"], v["b.txt"]["status"], v["c.txt"]["status"]) == ("OK", "CAMBIO", "FALTA")


def test_el_motor_corre_sobre_archivos_de_solo_lectura_y_el_hash_no_cambia(data_copy, built_profiles, key, tmp_path):
    """Archivos y carpeta sin permiso de escritura: el motor procesa igual y el SHA-256 no cambia."""
    import os
    import stat
    from nexus.audit import verify_hashes
    files = [p for p in data_copy.iterdir() if p.is_file()]
    for p in files:
        os.chmod(p, stat.S_IRUSR)
    os.chmod(data_copy, stat.S_IRUSR | stat.S_IXUSR)
    try:
        before = {p.name: sha(p) for p in files}
        res = run(data_copy, ic_tolerance_usd=key["tolerancia_intercompania_usd"], profiles_dir=built_profiles)
        d = write_run(res, tmp_path, source_dir=data_copy)
        registered = {k: v for k, v in res.input_hashes.items() if k in before}
        assert len(registered) >= 6 and registered == {k: before[k] for k in registered}   # registrado == real
        assert {p.name: sha(p) for p in files} == before
        assert all(v["status"] == "OK" for v in verify_hashes(res.input_hashes, [data_copy, built_profiles]).values())
        meta = json.loads(open(d + "/run.json", encoding="utf-8").read())["source"]
        assert meta["kind"] == "server_folder" and meta["mode"] == "read_only" and meta["network"] == "none"
        assert all(r.status == "MATCHED" for r in res.load_reports.values())
    finally:
        os.chmod(data_copy, stat.S_IRWXU)
        for p in files:
            os.chmod(p, stat.S_IRUSR | stat.S_IWUSR)


def test_el_motor_completo_corre_sin_ninguna_llamada_de_red(monkeypatch, built_profiles, key, tmp_path):
    """Se bloquea toda operacion de red; si el motor intentara una, la prueba falla."""
    import socket
    intentos = []

    def bloqueado(*a, **k):
        intentos.append(a)
        raise AssertionError("El motor intento usar la red")

    for name in ("create_connection", "getaddrinfo", "gethostbyname"):
        monkeypatch.setattr(socket, name, bloqueado)
    for name in ("connect", "connect_ex"):
        monkeypatch.setattr(socket.socket, name, bloqueado)
    res = run(DATA, ic_tolerance_usd=key["tolerancia_intercompania_usd"], profiles_dir=built_profiles)
    write_run(res, tmp_path, source_dir=DATA)
    assert intentos == [] and res.periods["2026-10"].summary["utilidad_neta"] > 0
