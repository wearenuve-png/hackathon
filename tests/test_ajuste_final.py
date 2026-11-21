"""Ajuste final: restablecer la demostracion, nombres del selector, estimaciones y guion."""
import hashlib
import os
import subprocess
import sys
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from conftest import DATA, ROOT
from nexus.pipeline import run
from nexus.ui import correcciones as CO

DEMO, PERF = ROOT / "data" / "demo_errores", ROOT / "data" / "demo_errores" / "perfiles"
BASE, DEMO_ESC = "Datos base", "Datos con errores (demostración)"
NOTA = "ya incluyen los 9 errores del reto"


def hashes():
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for d in (DATA, DEMO, ROOT / "profiles") for p in sorted(d.rglob("*")) if p.is_file()}


@pytest.fixture()
def app():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120).run()
    assert not at.exception, at.exception
    return at


def evento(quien="Ana"):
    return {"evento": "APROBAR", "quien": quien, "escenario": "x", "key": "k", "kind": "SIGNO", "ts": "t"}


def tx(at):
    return " ".join([m.value for m in at.markdown] + [w.value for w in at.warning] + [c.value for c in at.caption])


# ================================================================== 1. restablecer
def test_restablecer_deja_vacio_el_registro_y_no_toca_archivos(tmp_path):
    log = tmp_path / "a" / "log.jsonl"
    CO.registrar(log, evento())
    CO.registrar(log, evento("Beto"))
    antes = hashes()
    assert CO.restablecer(log) == 2
    assert log.exists() and log.read_text(encoding="utf-8") == "" and CO.leer(log) == []
    assert CO.restablecer(log) == 0 and CO.restablecer(tmp_path / "nuevo" / "x.jsonl") == 0       # idempotente
    assert hashes() == antes


def test_el_script_reset_demo_vacia_el_registro_y_verifica_los_hashes(tmp_path):
    log = tmp_path / "log.jsonl"
    CO.registrar(log, evento())
    antes = hashes()
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "reset_demo.py"), "--registro", str(log)],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    assert "1 evento(s) quitado(s)" in r.stdout and "Archivos fuente sin tocar" in r.stdout
    assert CO.leer(log) == [] and hashes() == antes
    CO.registrar(log, evento())                                                    # y por la variable de entorno
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "reset_demo.py")], capture_output=True, text=True,
                       timeout=60, env={**os.environ, "NEXUS_APROBACIONES": str(log)})
    assert r.returncode == 0 and CO.leer(log) == []


def test_el_boton_restablecer_vuelve_a_datos_base_y_vacia_el_registro(app):
    log = Path(os.environ["NEXUS_APROBACIONES"])
    assert any(b.key == "restablecer_btn" and b.label == "Restablecer demostración" for b in app.button)
    app.radio(key="escenario").set_value(DEMO_ESC).run()
    app.text_input(key="aprobador").set_value("Ana Prueba").run()
    antes = hashes()
    app.button(key="aprobar_SIGNO|EMP004|ferrex_el_salvador.xlsx|Income Statement|36").click().run()
    assert CO.leer(log) and any(m.label == "Resueltos" and m.value == "1" for m in app.metric)
    app.button(key="restablecer_btn").click().run()
    assert not app.exception, app.exception
    assert app.radio(key="escenario").value == BASE
    assert CO.leer(log) == []
    assert not [e for e in app.error if "errores sembrados" in e.value]               # sin banner de demostracion
    franja = " ".join(m.value for m in app.markdown if "nx-fig-v" in m.value)
    assert "1,985,000.00" in franja                                                   # vuelve la cifra base
    assert hashes() == antes                                                          # ningun archivo fuente cambio
    app.radio(key="escenario").set_value(DEMO_ESC).run()                              # y la demo arranca limpia
    assert any(m.label == "Resueltos" and m.value == "0" for m in app.metric)


def test_el_boton_restablecer_esta_arriba_junto_al_selector(app):
    assert "restablecer_btn" not in [b.key for b in app.sidebar.button]
    assert [r.key for r in app.main.radio][:1] == ["escenario"]


# ================================================================== 2. nombres y aclaracion
def test_el_selector_se_llama_datos_base_y_datos_con_errores(app):
    r = app.radio(key="escenario")
    assert list(r.options) == [BASE, DEMO_ESC] and r.value == BASE
    for t in [m.value for m in app.markdown] + [c.value for c in app.caption]:
        assert "Datos limpios" not in t


@pytest.mark.parametrize("escenario", [BASE, DEMO_ESC])
def test_el_resumen_aclara_que_los_datos_base_ya_traen_los_9_errores_del_reto(app, escenario):
    app.radio(key="escenario").set_value(escenario).run()
    notas = [c.value for c in app.caption if NOTA in c.value]
    assert len(notas) == 1
    if escenario == BASE:
        assert "tests/fixtures/ANSWER_KEY.md" in notas[0] and "verás hallazgos aunque no hayas alterado nada" in notas[0]
    else:
        assert "suma 7 errores más" in notas[0] and "data/demo_errores/ANSWER_KEY.md" in notas[0]


def test_los_9_errores_del_reto_son_9_en_la_clave():
    import json
    assert len(json.loads((ROOT / "tests" / "fixtures" / "answer_key.json").read_text(encoding="utf-8"))
               ["errores_sembrados"]) == 9


# ================================================================== 3. estimaciones
FRASE = "ESTIMACIÓN: requiere aprobación humana"


@pytest.fixture(scope="module")
def props():
    return {p.key: p for p in CO.proponer(run(DEMO, profiles_dir=PERF))}


def test_solo_las_estimaciones_llevan_la_etiqueta(props):
    est = {p.kind + ("|vacio" if p.valor_leido == "(vacío)" else ""): p for p in props.values() if p.estimacion}
    assert set(est) == {"IMPORTE|vacio", "TASA"}                                      # mediana del rubro y decimal corrido
    for p in est.values():
        assert p.motivo.startswith(FRASE + ".")
    for p in props.values():
        if not p.estimacion:
            assert FRASE not in p.motivo                                              # signo, «1O,000», asiento, moneda...
    texto = next(p for p in props.values() if p.valor_leido == "1O,000")
    assert not texto.estimacion and "letra O" in texto.motivo


def test_la_ficha_muestra_estimacion_para_el_monto_en_blanco_y_para_la_tasa(app):
    app.radio(key="escenario").set_value(DEMO_ESC).run()
    adv = [w.value for w in app.warning]
    assert adv.count(FRASE + ".") == 1                                                # octubre: el monto en blanco
    app.sidebar.radio[0].set_value("2026-12").run()
    assert [w.value for w in app.warning].count(FRASE + ".") == 1                     # diciembre: la tasa


def test_la_aprobacion_de_una_estimacion_deja_la_frase_en_el_registro_y_en_el_ajuste(props):
    p = next(x for x in props.values() if x.estimacion and x.kind == CO.IMPORTE)
    e = CO.evento_desde(p, "APROBAR", "Ana Prueba", "esc") | {"ts": "2026-11-21T12:00:00"}
    assert FRASE in e["motivo"] and e["valor_propuesto"] == "41000.00"
    c = CO.run_corregido(DEMO, PERF, [e])
    adj = next(a for a in c.adjustments if a.kind == "HUMAN_CORRECTION")
    assert FRASE in adj.reason and adj.approved_by == "Ana Prueba"


# ================================================================== 4. guion
def test_el_guion_trae_el_recorrido_de_la_demo_en_la_interfaz():
    g = (ROOT / "docs" / "GUION_DEMO.md").read_text(encoding="utf-8")
    plano = " ".join(g.split())
    i = g.index("## Recorrido de demo en la interfaz")
    sec = " ".join(g[i:g.index("## Recorrido por temas")].split())
    pasos = ("### Paso 1 · Datos base", "### Paso 2 · Cambio a datos con errores", "### Paso 3 · Un error de cada tipo",
             "### Paso 4 · Aprobar una corrección con nombre", "### Paso 5 · Vuelta a datos base")
    assert all(x in sec for x in pasos)
    assert [sec.index(x) for x in pasos] == sorted(sec.index(x) for x in pasos)          # el orden pedido
    for frag in ("1,985,000.00", "359,125.00", "Trazabilidad", "Ingresos por ventas (cuenta 4000)", NOTA.replace("ya incluyen",
                 "ya incluyen"), "DEMOSTRACIÓN", "ESTIMACIÓN: requiere aprobación humana", "Quién aprueba", "Aprobar corrección",
                 "Restablecer demostración", "scripts/reset_demo.py", "300,375.00", "355,325.00", "17 de 17"):
        assert frag in sec, frag
    for viejo in ("Alertas y exclusiones", "Resultados y balance", "Perfiles por empresa"):
        assert viejo not in plano                                                       # nombres de pestanas del rediseno
