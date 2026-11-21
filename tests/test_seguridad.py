"""Seguridad e integridad: manifiesto firmado, bitacora encadenada, garantias, FAQ como burbujas predefinidas."""
import hashlib
import json
import os
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from nexus.audit import sha256_file
from nexus.ui import correcciones as CO
from nexus.ui import seguridad as S

ROOT = Path(__file__).resolve().parent.parent
GEN = "0" * 64


def evento(quien="Ana"):
    return {"evento": "APROBAR", "quien": quien, "escenario": "esc", "key": "k1", "motivo": "m"}


def hashes_fuente():
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for d in ("data/synthetic", "data/demo_errores", "profiles") for p in sorted((ROOT / d).rglob("*")) if p.is_file()}


# ---------------------------------------------------------------- a) hashes de archivos y manifiesto
def test_sha256_conocido_y_un_byte_alterado_se_detecta(tmp_path):
    f = tmp_path / "a.csv"
    f.write_bytes(b"abc")
    assert sha256_file(f) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"   # SHA-256("abc"), valor publicado
    m = tmp_path / "man.json"
    S.guardar_manifiesto(m, tmp_path, {"a.csv": sha256_file(f)})
    assert S.comparar_manifiesto(m, {"a.csv": sha256_file(f)})["status"] == "IGUAL"
    f.write_bytes(b"abd")                                                                          # un solo byte
    c = S.comparar_manifiesto(m, {"a.csv": sha256_file(f)})
    assert c["status"] == "CAMBIO" and len(c["cambios"]) == 1
    x = c["cambios"][0]
    assert x["archivo"] == "a.csv" and x["antes"] == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    assert x["ahora"] == hashlib.sha256(b"abd").hexdigest() and x["antes"] != x["ahora"]


def test_manifiesto_primera_vez_agregado_falta_y_firma_alterada(tmp_path):
    m = tmp_path / "sub" / "man.json"
    assert S.comparar_manifiesto(m, {"a": "1"})["status"] == "NUEVO"
    man = S.guardar_manifiesto(m, "origen", {"a": "1", "b": "2"})
    assert man["firma"] == S._sha(S._canon({k: v for k, v in man.items() if k != "firma"}))
    tipos = {c["archivo"]: c["tipo"] for c in S.comparar_manifiesto(m, {"a": "1", "c": "3"})["cambios"]}
    assert tipos == {"b": "FALTA", "c": "AGREGADO"}
    d = json.loads(m.read_text())
    d["archivos"]["a"] = "9"                                                                       # editan el manifiesto
    m.write_text(json.dumps(d))
    assert S.comparar_manifiesto(m, {"a": "9", "b": "2"})["status"] == "ALTERADO"


# ---------------------------------------------------------------- b) bitacora encadenada
def test_la_cadena_se_calcula_a_mano_y_la_integra_pasa(tmp_path):
    log = tmp_path / "log.jsonl"
    e1 = CO.registrar(log, evento())
    e2 = CO.registrar(log, evento("Beto"))
    CO.registrar(log, evento("Carla"))
    l1, l2, _ = log.read_text(encoding="utf-8").splitlines()
    assert e1["prev"] == GEN                                                                       # primer eslabon
    sin = {k: v for k, v in e1.items() if k != "hash"}
    canon = json.dumps(sin, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    assert e1["hash"] == hashlib.sha256((GEN + canon).encode()).hexdigest()                         # a mano
    assert e2["prev"] == hashlib.sha256(l1.encode()).hexdigest()
    assert S.verificar_bitacora(log) == {"ok": True, "linea": None, "n": 3, "mensaje": "Bitácora íntegra"}
    assert [e["quien"] for e in CO.leer(log)] == ["Ana", "Beto", "Carla"]                            # leer sigue igual


def _log3(tmp_path):
    log = tmp_path / "log.jsonl"
    for q in ("Ana", "Beto", "Carla"):
        CO.registrar(log, evento(q))
    return log


def test_editar_una_linea_se_detecta_en_esa_linea(tmp_path):
    log = _log3(tmp_path)
    ls = log.read_text(encoding="utf-8").splitlines()
    ls[1] = ls[1].replace("Beto", "Mallory")
    log.write_text("\n".join(ls) + "\n", encoding="utf-8")
    v = S.verificar_bitacora(log)
    assert not v["ok"] and v["linea"] == 2 and v["mensaje"] == "Bitácora alterada en la línea 2"


def test_editar_la_ultima_linea_y_borrar_el_final_se_detectan(tmp_path):
    log = _log3(tmp_path)
    ls = log.read_text(encoding="utf-8").splitlines()
    log.write_text("\n".join(ls[:2] + [ls[2].replace("Carla", "X")]) + "\n", encoding="utf-8")
    assert S.verificar_bitacora(log)["linea"] == 3


def test_borrar_la_ultima_linea_o_una_del_medio_se_detecta(tmp_path):
    a = _log3(tmp_path)
    ls = a.read_text(encoding="utf-8").splitlines()
    a.write_text("\n".join(ls[:2]) + "\n", encoding="utf-8")                                        # borran la 3
    assert S.verificar_bitacora(a)["mensaje"] == "Bitácora alterada en la línea 3"
    d = tmp_path / "otro"
    d.mkdir()
    b = _log3(d)
    ls = b.read_text(encoding="utf-8").splitlines()
    b.write_text("\n".join([ls[0], ls[2]]) + "\n", encoding="utf-8")                                # borran la 2
    assert S.verificar_bitacora(b)["linea"] == 2


def test_reordenar_se_detecta(tmp_path):
    log = _log3(tmp_path)
    ls = log.read_text(encoding="utf-8").splitlines()
    log.write_text("\n".join([ls[1], ls[0], ls[2]]) + "\n", encoding="utf-8")
    v = S.verificar_bitacora(log)
    assert not v["ok"] and v["linea"] == 1


def test_compatibilidad_con_registros_anteriores_sin_hash(tmp_path):
    log = tmp_path / "log.jsonl"
    log.write_text(json.dumps({"ts": "x", **evento("Vieja")}) + "\n" + json.dumps({"ts": "y", **evento("Vieja2")}) + "\n",
                   encoding="utf-8")
    assert S.verificar_bitacora(log)["ok"]                                                          # solo heredados
    CO.registrar(log, evento("Nueva"))
    assert S.verificar_bitacora(log) == {"ok": True, "linea": None, "n": 3, "mensaje": "Bitácora íntegra"}
    ls = log.read_text(encoding="utf-8").splitlines()
    log.write_text("\n".join([ls[0], ls[1].replace("Vieja2", "Zeta"), ls[2]]) + "\n", encoding="utf-8")
    assert S.verificar_bitacora(log)["linea"] == 3                                                  # el eslabon siguiente delata
    assert [e["quien"] for e in CO.leer(log)][0] == "Vieja"


def test_restablecer_deja_una_cadena_valida_y_vacia(tmp_path):
    log = _log3(tmp_path)
    CO.restablecer(log)
    assert S.verificar_bitacora(log)["ok"] and S.verificar_bitacora(log)["n"] == 0
    assert CO.registrar(log, evento())["prev"] == GEN and S.verificar_bitacora(log)["ok"]


def test_bitacora_inexistente_es_integra(tmp_path):
    assert S.verificar_bitacora(tmp_path / "no.jsonl")["ok"]


# ---------------------------------------------------------------- c) garantias
def test_garantias_cumplen_en_este_repositorio():
    g = S.garantias(6, 6)
    assert [x["Estado"] for x in g] == ["Cumple"] * 3
    assert S.motor_sin_red() == [] and S.llave_fuera_del_repo()["archivos_con_llave"] == []


def test_detecta_un_import_de_red_y_una_llave_expuesta(tmp_path):
    (tmp_path / "nexus").mkdir()
    (tmp_path / "nexus" / "mal.py").write_text("import requests\n")
    (tmp_path / "nexus" / "bien.py").write_text("import json\n")
    (tmp_path / "cfg.json").write_text('{"k": "sk-ant-' + "A" * 50 + '"}')     # llave de mentira, armada al vuelo
    assert S.motor_sin_red(tmp_path) == ["nexus/mal.py"]
    assert S.llave_fuera_del_repo(tmp_path)["archivos_con_llave"] == ["cfg.json"]
    assert S.llave_fuera_del_repo(tmp_path)["gitignore_ok"] is False


# ---------------------------------------------------------------- d) tabla honesta + interfaz
PROHIBIDAS = ("antivirus", "firewall", "ciberataque")


def test_la_tabla_es_honesta_y_no_usa_palabras_prohibidas():
    der = " ".join(x[1] for x in S.TABLA_ALCANCE).lower()
    assert "malware" in der and "intrusión" in der and "acceso físico" in der
    texto = (ROOT / "nexus/ui/seguridad.py").read_text(encoding="utf-8").lower() + \
        (ROOT / "nexus/ui/panel_seguridad.py").read_text(encoding="utf-8").lower()
    assert not any(p in texto for p in PROHIBIDAS) and "protege de" not in texto


@pytest.fixture()
def app():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120)
    at.run()
    return at


def ir(at, seccion):
    at.radio(key="nav").set_value(seccion).run()
    assert not at.exception, (seccion, at.exception)
    return at


def todo(at):
    return " ".join(x.value for x in list(at.markdown) + list(at.success) + list(at.error) + list(at.info) +
                    list(at.warning) + list(at.caption))


def test_panel_en_la_app_sin_cambios_y_los_fuente_no_se_tocan(app):
    antes = hashes_fuente()
    ir(app, "Perfiles e integridad")
    t = todo(app)
    assert "Seguridad e integridad" in t and "Qué protege / Qué NO protege" in t
    assert "Bitácora íntegra" in t and "Primera ejecución" in t
    app.run()                                                                                       # segunda ejecucion: ya hay manifiesto
    assert "Sin cambios: las" in todo(app) and not app.exception
    assert not any(p in todo(app).lower() for p in PROHIBIDAS)
    assert hashes_fuente() == antes


def test_panel_avisa_con_archivo_y_los_dos_hashes_y_la_bitacora_alterada(app):
    ir(app, "Perfiles e integridad")
    app.run()                                                                                       # manifiesto guardado
    mp = S.manifiesto_path(ROOT / "data" / "synthetic")
    m = json.loads(mp.read_text())
    nombre = sorted(m["archivos"])[0]
    viejo = m["archivos"][nombre]
    m["archivos"][nombre] = "a" * 64                                                                 # simula que cambio
    m["firma"] = S._firma(m)
    mp.write_text(json.dumps(m))
    app.run()
    t = todo(app)
    assert "sin que se declarara el cambio" in t
    fila = next(f for f in (d.value for d in app.dataframe) if "Huella anterior" in f.columns)
    r = fila[fila["Archivo"] == nombre].iloc[0]
    assert r["Huella anterior"] == "a" * 64 and r["Huella ahora"] == viejo
    # bitacora alterada
    log = CO.log_por_defecto()
    CO.registrar(log, evento())
    log.write_text(log.read_text(encoding="utf-8").replace("Ana", "Eva"), encoding="utf-8")
    app.run()
    assert "Bitácora alterada en la línea 1" in todo(app)


def test_faq_es_un_mini_chat_de_burbujas_predefinidas(app):
    from nexus.ui.tab_ayuda import FAQ
    ir(app, "Ayuda")
    t = todo(app)
    assert "Preguntas frecuentes · respuestas predefinidas" in t
    assert len(app.chat_input) == 0 and len(app.chat_message) == 0
    botones = [b for b in app.button if b.key and b.key.startswith("faq_") and b.key != "faq_limpiar"]
    assert len(botones) == len(FAQ)
    next(b for b in botones if b.key == "faq_1").click().run()
    assert len(app.chat_message) == 2 and not app.exception
    burbujas = [[x.value for x in m.markdown] for m in app.chat_message]
    assert burbujas[0] == [FAQ[1][0]] and burbujas[1][-1] == FAQ[1][1]
    assert len(app.chat_input) == 0
