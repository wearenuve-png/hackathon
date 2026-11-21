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
    ajeno = trabajo / "carpeta_del_usuario"                   # sin marca de NEXUS: no se borra
    ajeno.mkdir()
    r = RS.limpiar_todo(log, man, trabajo)
    assert r == {"eventos": 1, "manifiestos": 1, "copias": 1}
    assert CO.leer(log) == [] and not list(man.glob("*.json")) and ajeno.is_dir()
    assert (hashes(a), hashes(b)) == antes
    assert RS.limpiar_todo(log, man, trabajo) == {"eventos": 0, "manifiestos": 0, "copias": 0}      # idempotente


# ---------------------------------------------------------------- interfaz
def nuevo():
    at = AppTest.from_file(APP, default_timeout=120).run()
    assert not at.exception, at.exception
    return at


def textos(at):
    return " ".join(x.value for x in list(at.markdown) + list(at.info) + list(at.warning) + list(at.caption))


def test_el_boton_restablecer_ya_no_dice_demostracion_y_hay_boton_de_cargar():
    at = nuevo()
    assert [b.label for b in at.button if b.key == "restablecer_btn"] == ["Restablecer"]
    assert any(b.key == "carga_btn" and b.label == "Cargar presupuestos" for b in at.button)


def test_cargar_carpetas_llena_la_pantalla_y_restablecer_vuelve_al_ejemplo(tmp_path):
    a, b = reparto(tmp_path)
    antes = (hashes(a), hashes(b))
    at = nuevo()
    at.button(key="carga_btn").click().run()
    at.text_area(key="carga_rutas").set_value(f"{a}\n{b}").run()
    at.button(key="carga_leer").click().run()
    assert not at.exception, at.exception
    assert any("Mostrando tus presupuestos de" in i.value for i in at.info)
    franja = " ".join(m.value for m in at.markdown if "nx-fig-v" in m.value)
    assert "Utilidad neta" in franja and "355,294.95" in franja
    assert "Los datos base ya incluyen" not in textos(at) and "NEXUS no conoce sus errores" in textos(at)
    for sec in ("Estados financieros", "Alertas y errores", "Hallazgos", "Intercompañía", "Trazabilidad", "Indicadores",
                "Variaciones", "Simulador", "Perfiles e integridad", "Ayuda", "Asistente"):
        at.radio(key="nav").set_value(sec).run()
        assert not at.exception, (sec, at.exception)
        assert "falló" not in textos(at)
    at.button(key="restablecer_btn").click().run()
    assert not at.exception and not any("Mostrando tus presupuestos" in i.value for i in at.info)
    assert not [m for m in at.markdown if '<div class="nx-fig-v' in m.value] and not at.dataframe       # todo en blanco
    assert "Sin datos cargados" in textos(at) and len(at.radio) == 0
    at.button(key="ejemplo_base").click().run()                                       # los datos de ejemplo siguen ahi
    assert "1,985,000.00" in " ".join(m.value for m in at.markdown if "nx-fig-v" in m.value)
    assert (hashes(a), hashes(b)) == antes


def test_carpeta_incompleta_muestra_aviso_amable(tmp_path):
    a, _ = reparto(tmp_path)
    at = nuevo()
    at.button(key="carga_btn").click().run()
    at.text_area(key="carga_rutas").set_value(str(a)).run()
    at.button(key="carga_leer").click().run()
    assert not at.exception
    assert any("Falta la configuración del grupo" in w.value for w in at.warning)
    assert not any("Mostrando tus presupuestos" in i.value for i in at.info)


def test_restablecer_deja_todo_en_blanco_y_se_puede_cargar_de_nuevo(tmp_path):
    a, b = reparto(tmp_path)
    at = nuevo()
    assert [m for m in at.markdown if '<div class="nx-fig-v' in m.value]                           # hay datos al abrir
    at.button(key="restablecer_btn").click().run()
    assert not at.exception, at.exception
    assert not [m for m in at.markdown if '<div class="nx-fig-v' in m.value]
    assert not at.dataframe and not at.metric and not at.get("download_button")        # sin tablas, metricas ni paquete
    assert [x.key for x in at.button if x.key in ("ejemplo_base", "ejemplo_demo", "carga_btn", "restablecer_btn")] == [
        "restablecer_btn", "carga_btn", "ejemplo_base", "ejemplo_demo"]
    at.button(key="carga_btn").click().run()                                           # cargar carpetas sale del blanco
    at.text_area(key="carga_rutas").set_value(f"{a}\n{b}").run()
    at.button(key="carga_leer").click().run()
    assert "355,294.95" in " ".join(m.value for m in at.markdown if "nx-fig-v" in m.value)
