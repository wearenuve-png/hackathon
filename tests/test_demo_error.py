"""Demostracion de errores: se aplica a una COPIA temporal; los originales no cambian; cada caso da la causa esperada."""
import glob
import hashlib
import tempfile
from decimal import Decimal
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from conftest import DATA, KEY, ROOT
from nexus.pipeline import run
from nexus.ui import demo_error as DE

D = Decimal
PROFILES = ROOT / "profiles"
CASOS = ["borrar", "signo", "duplicar"]


def hashes():
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for d in (DATA, PROFILES) for p in sorted(d.iterdir()) if p.is_file()}


def tmp_demo():
    return set(glob.glob(str(Path(tempfile.gettempdir()) / "nexus_demo_*")))


@pytest.fixture()
def caso():
    hechos = []

    def hacer(nombre):
        d = DE.correr(DE.preparar(nombre, DATA, PROFILES))
        hechos.append(d)
        return d
    yield hacer
    for d in hechos:
        DE.limpiar(d.tmp_dir)


# ================================================================== originales intactos
@pytest.mark.parametrize("nombre", CASOS)
def test_los_originales_no_cambian_y_la_copia_es_otra_carpeta(caso, nombre):
    antes = hashes()
    d = caso(nombre)
    assert hashes() == antes                                                   # ni los datos ni los perfiles
    for p in (d.data_dir, d.profiles_dir):
        assert ROOT not in p.parents or "nexus_demo_" in str(p)                # fuera del proyecto
    assert DATA not in d.data_dir.parents and d.data_dir != DATA
    archivo = d.extras["archivo"]
    copia = (d.data_dir / archivo).read_text(encoding="cp1252")
    original = (DATA / archivo).read_text(encoding="cp1252")
    assert "Banco de demostracion" in copia or nombre != "duplicar"           # lo alterado esta SOLO en la copia
    assert len(copia.splitlines()) > len(original.splitlines())
    assert copia.startswith(original.rstrip("\r\n"))                           # el resto de la copia es identico
    DE.limpiar(d.tmp_dir)
    assert not d.tmp_dir.exists() and hashes() == antes


def test_los_datos_reales_siguen_sin_balance_descuadrado(caso):
    real = run(DATA, ic_tolerance_usd=KEY["tolerancia_intercompania_usd"], profiles_dir=PROFILES)
    antes = {p: dict(pr.summary) for p, pr in real.periods.items()}
    caso("borrar")
    assert not [f for f in real.findings if f.rule_id == "BAL-01"]
    assert {p: pr.summary for p, pr in real.periods.items()} == antes
    for p in real.periods:
        assert real.periods[p].summary["activo_menos_pasivo_y_patrimonio"] == 0


# ================================================================== causa esperada de cada caso
def test_caso1_borrar_un_asiento_de_8000(caso):
    d = caso("borrar")
    f = d.ficha
    assert f is not None and f.diferencia == D("-8000")                       # activo - (pasivo + patrimonio)
    assert d.run.periods[d.period].summary["activo_menos_pasivo_y_patrimonio"] == D("-8000")
    assert [(c.orden, c.tipo) for c in f.candidatos] == [(1, "REGISTRO_IGUAL_A_D")]
    assert [u.account_local for u in f.candidatos[0].registros] == ["Cuentas por pagar"]
    assert d.detectada and d.candidata_orden == 1
    assert DE.ficha_para_demo(d).candidatos[0].tipo == "REGISTRO_IGUAL_A_D"    # causa correcta primero


def test_caso2_invertir_el_signo_de_un_registro_de_4000(caso):
    d = caso("signo")
    f = d.ficha
    assert f.diferencia == D("-8000")                                          # 4,000 x 2
    assert [(c.orden, c.tipo) for c in f.candidatos] == [(2, "SIGNO_INVERTIDO")]
    importes = sorted(u.importe for u in f.candidatos[0].registros)
    assert importes[0] == -importes[1] and importes[1] == D("4000") / D("0.05")   # +-80,000 MXN
    assert d.detectada and d.candidata_orden == 2
    assert DE.ficha_para_demo(d).candidatos[0].tipo == "SIGNO_INVERTIDO"
    assert not any(c.orden == 1 for c in f.candidatos)                         # ningun registro de 8,000


def test_caso3_duplicar_un_registro_de_8000(caso):
    d = caso("duplicar")
    f = d.ficha
    assert f.diferencia == D("8000")
    dup = next(c for c in f.candidatos if c.tipo == "DUPLICADO")
    assert dup.orden == 3 and len(dup.registros) == 2 and {u.account_local for u in dup.registros} == {"Caja"}
    assert d.detectada and d.candidata_orden == 3
    # el motor numera primero la candidata generica (registro igual a D); la demo muestra primero la correcta
    assert f.candidatos[0].tipo == "REGISTRO_IGUAL_A_D"
    en_demo = DE.ficha_para_demo(d)
    assert en_demo.candidatos[0].tipo == "DUPLICADO" and en_demo.candidatos[0].orden == 3   # sin renumerar
    assert any(x.rule_id == "DUP-02" for x in d.run.findings)                  # y se marca como posible duplicado


@pytest.mark.parametrize("nombre", CASOS)
def test_la_ficha_es_de_balance_con_causa_probable_y_accion_humana(caso, nombre):
    f = caso(nombre).ficha
    assert f.tipo == "BALANCE_DESCUADRADO" and "hipótesis" in f.causa_probable and "Causa candidata" in f.causa_probable
    assert "empresa" in f.accion.lower() and f.donde


def test_la_copia_se_arma_con_la_tasa_del_periodo(caso):
    d = caso("duplicar")
    cop = [u for c in d.ficha.candidatos for u in c.registros if u.account_local == "Caja"]
    assert cop and all(u.usd == D("8000") for u in cop if u.status == "OK")   # 160,000 MXN x 0.05


def test_si_la_demostracion_no_puede_prepararse_no_deja_carpetas(tmp_path):
    antes = tmp_demo()
    cfg = DE.cargar_config()
    cfg["empresa"] = "EMP999"
    with pytest.raises(KeyError):
        DE.preparar("borrar", DATA, PROFILES, cfg)
    assert tmp_demo() == antes
    cfg2 = DE.cargar_config()
    cfg2["empresa"] = "EMP001"                                                 # EMP001 es XLSX: no se sabe alterar
    with pytest.raises(ValueError, match="solo sabe alterar archivos CSV"):
        DE.preparar("borrar", DATA, PROFILES, cfg2)
    assert tmp_demo() == antes


# ================================================================== la interfaz ya no tiene esta demostracion
@pytest.fixture()
def app():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120).run()
    assert not at.exception, at.exception
    return at


def test_la_demostracion_anterior_ya_no_esta_en_la_interfaz(app):
    assert not [b for b in app.selectbox if b.key == "demo_caso" or b.label == "Demostración de errores"]
    assert not [e for e in app.error if "datos alterados en una copia temporal" in e.value]
    assert not [m for m in app.markdown if "Demostración de errores" in m.value]
    assert not [b for b in app.button if b.key == "demo_volver"]


def test_el_diagnostico_de_balance_de_la_demostracion_anterior_se_ve_en_el_escenario_nuevo(app):
    """Los casos de 8,000 (omitido / duplicado) y 4,000 (signo) ahora viven en data/demo_errores: el asiento omitido
    descuadra el balance de EMP006 en 2026-12 y la ficha lista como primera candidata el registro igual al desbalance."""
    from conftest import DEMO_ERR, DEMO_ERR_PERF, cargar
    cargar(app, DEMO_ERR, DEMO_ERR_PERF)
    app.sidebar.radio[0].set_value("2026-12").run()
    app.radio(key="nav").set_value("Hallazgos").run()
    tx = " ".join(m.value for m in app.markdown)
    assert "Balance descuadrado" in " ".join(e.label for e in app.expander if e.label.startswith("FCH-"))
    assert "Causas candidatas del desbalance" in tx and "cuyo importe es igual al desbalance (8,000.00 USD)" in tx
