"""Cargar presupuestos desde carpetas (una o varias) y boton Restablecer. Los originales nunca cambian."""
import hashlib
import json
import os
import shutil
from decimal import Decimal
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from nexus.pipeline import run
from nexus.ui import carga_auto as CA
from nexus.ui import correcciones as CO
from nexus.ui import restablecer as RS
from nexus.ui import seguridad as SG

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "data" / "demo"                      # de Mateo; el LEEME trae las utilidades verificadas
UTILIDAD = {"2026-10": Decimal("355294.95375"), "2026-11": Decimal("172407.72400"), "2026-12": Decimal("224288")}
APP = str(ROOT / "app.py")


def hashes(d):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(d).iterdir()) if p.is_file()}


def reparto(tmp_path):
    """Pone los presupuestos en una carpeta y la configuracion en otra."""
    a, b = tmp_path / "presupuestos", tmp_path / "config"
    a.mkdir(), b.mkdir()
    for f in DEMO.iterdir():
        if f.is_file() and f.name != "LEEME_DEMO.md":
            shutil.copy2(f, b if f.name in CA.CONFIG else a)
    return a, b


def utilidades(res):
    return {p: pr.summary["utilidad_neta"] for p, pr in res.periods.items()}


def test_una_carpeta_completa_se_usa_tal_cual_y_da_las_cifras_del_leeme(tmp_path):
    antes = hashes(DEMO)
    r = CA.preparar([str(DEMO)], tmp_path)
    assert r["ok"] and r["dir"] == str(DEMO.resolve()) and not r["copiado"] and not r["problemas"]
    res = run(r["dir"])
    assert utilidades(res) == UTILIDAD                       # 355,294.95 / 172,407.72 / 224,288.00 (LEEME de Mateo)
    assert hashes(DEMO) == antes


def test_varias_carpetas_dan_el_mismo_resultado_y_los_originales_no_cambian(tmp_path):
    a, b = reparto(tmp_path)
    antes = (hashes(a), hashes(b))
    r = CA.preparar([str(a), str(b)], tmp_path / "trabajo")
    assert r["ok"] and r["copiado"] and (Path(r["dir"]) / CA.MARCA).is_file()
    assert utilidades(run(r["dir"])) == UTILIDAD
    assert (hashes(a), hashes(b)) == antes


def test_falta_configuracion_o_un_presupuesto_se_explica_sin_error_tecnico(tmp_path):
    a, b = reparto(tmp_path)
    r = CA.preparar([str(a)], tmp_path / "t")
    assert not r["ok"] and "tasas.csv" in r["problemas"][0] and "no adivina" in r["problemas"][0]
    (a / "ferrex_mexico.xlsx").unlink()
    r = CA.preparar([str(a), str(b)], tmp_path / "t")
    assert not r["ok"] and "ferrex_mexico.xlsx" in " ".join(r["problemas"])
    for texto in CA.preparar(["/no/existe", ""], tmp_path)["problemas"] + CA.preparar([], tmp_path)["problemas"]:
        assert "Traceback" not in texto and "Error" not in texto


def test_mismo_nombre_con_contenido_distinto_se_avisa(tmp_path):
    a, b = reparto(tmp_path)
    shutil.copy2(a / "ferrex_mexico.xlsx", b / "ferrex_mexico.xlsx")
    (b / "ferrex_mexico.xlsx").write_bytes(b"otro contenido")
    r = CA.preparar([str(a), str(b)], tmp_path / "t")
    assert not r["ok"] and any("dos carpetas con contenido distinto" in p for p in r["problemas"])


def test_limpiar_todo_borra_lo_del_programa_y_no_toca_presupuestos(tmp_path):
    a, b = reparto(tmp_path)
    antes = (hashes(a), hashes(b))
    log, man, trabajo = tmp_path / "log.jsonl", tmp_path / "man", tmp_path / "trabajo"
    CO.registrar(log, {"evento": "APROBAR", "quien": "Ana", "escenario": "e", "key": "k"})
    SG.guardar_manifiesto(man / "manifiesto_x.json", "x", {"a": "1"})
    CA.preparar([str(a), str(b)], trabajo)
    ajeno = trabajo / "carpeta_del_usuario"                   # sin marca de FinaCore: no se borra
    ajeno.mkdir()
    r = RS.limpiar_todo(log, man, trabajo)
    assert r == {"eventos": 1, "manifiestos": 1, "copias": 1}
    assert CO.leer(log) == [] and not list(man.glob("*.json")) and ajeno.is_dir()
    assert (hashes(a), hashes(b)) == antes
    assert RS.limpiar_todo(log, man, trabajo) == {"eventos": 0, "manifiestos": 0, "copias": 0}      # idempotente


# ---------------------------------------------------------------- interfaz (arranca en blanco)
@pytest.fixture()
def nuevo(monkeypatch):
    monkeypatch.setenv("NEXUS_TEST_SIN_CARGA", "1")
    at = AppTest.from_file(APP, default_timeout=120).run()
    assert not at.exception, at.exception
    return at


def textos(at):
    return " ".join(x.value for x in list(at.markdown) + list(at.info) + list(at.warning) + list(at.caption))


def figuras(at):
    return [m for m in at.markdown if '<div class="nx-fig-v' in m.value]


def cargar_carpetas(at, rutas):
    if not any(t.key == "carga_rutas" for t in at.text_area):
        at.button(key="carga_btn").click().run()
    at.text_area(key="carga_rutas").set_value(rutas).run()
    at.button(key="carga_leer").click().run()
    assert not at.exception, at.exception


def test_sin_cargar_nada_no_se_ve_nada_y_no_existe_ningun_dato_de_demostracion(nuevo):
    assert not figuras(nuevo) and not nuevo.dataframe and not nuevo.metric and not nuevo.get("download_button")
    assert len(nuevo.radio) == 0 and "Sin datos cargados" in textos(nuevo)
    assert [b.label for b in nuevo.button if b.key == "restablecer_btn"] == ["Restablecer"]
    assert any(b.key == "carga_btn" and b.label == "Cargar presupuestos" for b in nuevo.button)
    assert any(t.key == "carga_rutas" for t in nuevo.text_area)                         # el panel de carga ya esta abierto
    todo = textos(nuevo)
    for palabra in ("Datos base", "demostración", "DEMOSTRACIÓN", "Usar datos", "errores sembrados", "sintétic"):
        assert palabra not in todo, palabra
    assert not [b for b in nuevo.button if b.key in ("ejemplo_base", "ejemplo_demo")]


def test_cargar_carpetas_llena_la_pantalla_y_restablecer_la_deja_en_blanco(nuevo, tmp_path):
    a, b = reparto(tmp_path)
    antes = (hashes(a), hashes(b))
    cargar_carpetas(nuevo, f"{a}\n{b}")
    assert any("Mostrando tus presupuestos de" in i.value for i in nuevo.info)
    franja = " ".join(m.value for m in nuevo.markdown if "nx-fig-v" in m.value)
    assert "Utilidad neta" in franja and "355,294.95" in franja
    assert "no conoce sus errores" in textos(nuevo)
    for sec in ("Estados financieros", "Alertas y errores", "Hallazgos", "Intercompañía", "Trazabilidad", "Indicadores",
                "Variaciones", "Simulador", "Perfiles e integridad", "Ayuda", "Asistente"):
        nuevo.radio(key="nav").set_value(sec).run()
        assert not nuevo.exception, (sec, nuevo.exception)
        assert "falló" not in textos(nuevo)
    nuevo.button(key="restablecer_btn").click().run()
    assert not nuevo.exception and not any("Mostrando tus presupuestos" in i.value for i in nuevo.info)
    assert not figuras(nuevo) and not nuevo.dataframe and len(nuevo.radio) == 0 and "Sin datos cargados" in textos(nuevo)
    assert (hashes(a), hashes(b)) == antes                                             # tus archivos siguen intactos


def test_los_errores_de_los_archivos_cargados_se_identifican_y_se_explican(nuevo, tmp_path):
    a, b = reparto(tmp_path)
    cargar_carpetas(nuevo, f"{a}\n{b}")
    nuevo.radio(key="nav").set_value("Hallazgos").run()
    fichas = [e.label for e in nuevo.expander if e.label.startswith("FCH-")]
    assert fichas                                                                      # el motor detecto errores en la carga
    nuevo.radio(key="nav").set_value("Asistente").run()
    nuevo.button(key="asist_revisar").click().run()                                    # modo local: sin llave, plantillas
    texto = " ".join(m.value for m in nuevo.markdown)
    assert "Qué pasó:" in texto and "Dónde:" in texto and "Causa probable:" in texto and "Qué decidir:" in texto
    assert all(f.split(" ")[0] in texto for f in fichas[:3])                           # cita las fichas
    assert not nuevo.exception


def test_carpeta_incompleta_muestra_aviso_amable_y_sigue_en_blanco(nuevo, tmp_path):
    a, _ = reparto(tmp_path)
    cargar_carpetas(nuevo, str(a))
    assert any("Falta la configuración del grupo" in w.value for w in nuevo.warning)
    assert not any("Mostrando tus presupuestos" in i.value for i in nuevo.info) and not figuras(nuevo)


def test_una_carpeta_con_perfiles_los_usa(nuevo):
    from conftest import DEMO_ERR
    cargar_carpetas(nuevo, str(DEMO_ERR))
    nuevo.radio(key="nav").set_value("Perfiles e integridad").run()
    perf = next(d.value for d in nuevo.dataframe if "Ultima carga" in d.value.columns)
    assert "Coincide con el perfil" in set(perf["Ultima carga"])
