"""Integracion: diseno de feat/ui (Sergio) + todo lo de main. Recorre la app completa (menu horizontal de Sergio, key "nav") y verifica que no hay
errores, que las cifras en pantalla son las de answer_key.json y que los archivos originales no cambian."""
import hashlib
from decimal import ROUND_HALF_UP, Decimal

import pytest
from streamlit.testing.v1 import AppTest

from conftest import DATA, KEY, ROOT

APP = str(ROOT / "app.py")
PERIODOS = sorted(KEY["consolidado_esperado_usd"])
SECCIONES = ["Inicio", "Estados financieros", "Alertas y errores", "Hallazgos", "Intercompañía", "Trazabilidad",
             "Indicadores", "Variaciones", "Simulador", "Perfiles e integridad", "Ayuda", "Asistente"]
CARPETAS = {"synthetic": ROOT / "profiles", "demo_errores": ROOT / "data" / "demo_errores" / "perfiles", "demo": None}
FALLA = ("falló", "No se pudo", "no define render", "Traceback", "Exception", "Próximamente")


def fmt(s):
    return f"{Decimal(s).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):,.2f}"


def hashes():
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for d in (DATA, ROOT / "profiles") for p in sorted(d.iterdir()) if p.is_file()}


def textos(at):
    return [m.value for m in at.markdown] + [e.value for e in at.error] + [w.value for w in at.warning] + \
           [i.value for i in at.info] + [s.value for s in at.success] + [c.value for c in at.caption] + \
           [h.value for h in at.subheader]


def tablas(at):
    return [d.value for d in at.dataframe]


@pytest.fixture()
def app():
    at = AppTest.from_file(APP, default_timeout=120).run()
    assert not at.exception, at.exception
    return at


def ir(at, seccion):
    at.radio(key="nav").set_value(seccion).run()
    assert not at.exception, (seccion, at.exception)
    return at


def en_periodo(at, periodo):
    at.sidebar.radio[0].set_value(periodo).run()
    assert not at.exception, at.exception
    return at


# ================================================================== recorre todas las secciones
@pytest.mark.parametrize("carpeta", list(CARPETAS))
@pytest.mark.parametrize("periodo", PERIODOS)
def test_ninguna_seccion_muestra_errores_en_ningun_periodo_ni_carpeta(app, periodo, carpeta):
    from conftest import cargar
    cargar(app, ROOT / "data" / carpeta, CARPETAS[carpeta])
    at = en_periodo(app, periodo)
    nav = at.radio(key="nav")
    assert len(nav.options) == len(SECCIONES) and len(at.tabs) == 0
    for sec in SECCIONES:
        ir(at, sec)
        for t in textos(at):
            for palabra in FALLA:
                assert palabra not in t, f"{carpeta} {periodo} {sec}: aparece '{palabra}' en: {t[:120]}"


@pytest.mark.parametrize("periodo", PERIODOS)
def test_todo_lo_de_main_esta_accesible(app, periodo):
    at = en_periodo(app, periodo)
    tx = " ".join(textos(at))
    assert "Resumen de la carga" in tx                                                # Inicio
    assert "Nivel de confianza" in tx and any(m.label == "Registros limpios" for m in at.metric)
    assert len(at.get("download_button")) == 1                                       # paquete de auditoria (barra lateral)
    tx = " ".join(textos(ir(at, "Indicadores")))
    assert "Indicadores de rentabilidad" in tx and any(m.label == "ROIC (mensual)" for m in at.metric)
    assert "Variaciones: ¿por qué cambió cada cifra?" in " ".join(textos(ir(at, "Variaciones")))
    assert "Hallazgos: qué pasó, dónde, por qué importa y qué hacer" in " ".join(textos(ir(at, "Hallazgos")))
    ir(at, "Simulador")
    assert "Simulador de tipo de cambio" in " ".join(textos(at)) and any("SIMULACIÓN" in e.value for e in at.error)
    ir(at, "Ayuda")
    assert any(e.label == "PROVISIONAL" for e in at.expander)
    assert len(at.chat_input) == 1                                                   # chat local de la Ayuda
    assert "Seguridad e integridad" in " ".join(textos(ir(at, "Perfiles e integridad")))
    assert any("Asistente NEXUS (prototipo)" in c.value for c in ir(at, "Asistente").caption)


def test_variaciones_primer_periodo_avisa_y_los_demas_comparan(app):
    primero = ir(en_periodo(app, PERIODOS[0]), "Variaciones")
    assert any("primer periodo" in i.value for i in primero.info)
    nov = ir(en_periodo(app, PERIODOS[1]), "Variaciones")
    tx = " ".join(m.value for m in nov.markdown)
    assert "La utilidad neta consolidada baja 80,315.00 USD" in tx
    assert any(i.value.startswith("Operación se mide sobre todo lo cargado y valorable") for i in nov.info)


# ================================================================== cifras en pantalla = answer_key.json
@pytest.mark.parametrize("periodo", PERIODOS)
def test_las_cifras_en_pantalla_son_las_de_la_clave(app, periodo):
    at = ir(en_periodo(app, periodo), "Estados financieros")
    exp = KEY["consolidado_esperado_usd"][periodo]["resumen"]
    estado = next(t for t in tablas(at) if {"Concepto", "Suma de empresas", "Consolidado"} <= set(t.columns)
                  and "Ingresos" in set(t["Concepto"]))
    por = dict(zip(estado["Concepto"], estado["Consolidado"]))
    assert por["Ingresos"] == fmt(exp["ingresos"]) and por["= Utilidad neta"] == fmt(exp["utilidad_neta"])
    # la franja de cifras del encabezado (HTML de feat/ui) muestra los mismos numeros
    franja = " ".join(m.value for m in at.markdown if "nx-fig-v" in m.value)
    assert fmt(exp["ingresos"]) in franja
    naive = KEY["suma_ingenua_sin_eliminar_usd"][periodo]["ingresos"]
    assert por.get("Ingresos") and fmt(naive) in " ".join(estado[estado["Concepto"] == "Ingresos"]["Suma de empresas"])


def test_octubre_ingresos_1985000_y_utilidad_359125(app):
    at = ir(en_periodo(app, "2026-10"), "Estados financieros")
    franja = " ".join(m.value for m in at.markdown if "nx-fig-v" in m.value)
    assert "1,985,000.00" in franja
    estado = next(t for t in tablas(at) if "Suma de empresas" in t.columns and "Ingresos" in set(t["Concepto"]))
    fila = estado[estado["Concepto"] == "= Utilidad neta"].iloc[0]
    assert fila["Consolidado"] == "359,125.00" and fila["Suma de empresas"] == "359,125.00"
    assert estado[estado["Concepto"] == "Ingresos"].iloc[0]["Suma de empresas"] == "2,078,000.00"   # suma ingenua


# ================================================================== mejoras de presentacion conservadas
def test_intercompania_en_una_sola_fila_con_explicacion(app):
    at = ir(en_periodo(app, "2026-11"), "Intercompañía")
    ic = next(t for t in tablas(at) if "Afecta" in t.columns and "Diferencia" in t.columns)
    assert len(ic) == 1 and ic.iloc[0]["Afecta"] == "operación (venta) y saldo (CxC y CxP)"
    assert ic.iloc[0]["Diferencia"] == "2,000.00" and ic.iloc[0]["Referencia"] == "DC-IC-2611-MX"
    assert any("una sola vez" in c.value for c in at.caption)
    franja = " ".join(m.value for m in at.markdown if "nx-fig-v" in m.value)
    assert 'Diferencias entre empresas</div><div class="nx-fig-v amber">1</div>' in franja   # el conteo tambien es 1, no 2


def test_rotulo_ingresos_por_ventas_cuenta_4000_y_aclaracion(app):
    ir(app, "Trazabilidad")
    next(b for b in app.selectbox if b.label == "Cifra").select("Ingresos por ventas (cuenta 4000)").run()
    assert not app.exception
    nota = [c.value for c in app.caption if c.value.startswith("Esta cifra es solo la cuenta 4000")]
    assert len(nota) == 1 and "1,985,000.00" in nota[0] and "otras cuentas de ingresos" in nota[0]


def test_provisional_y_hashes_de_integridad_visibles(app):
    assert any("PROVISIONAL" in e.value for e in app.error)
    integ = next(t for t in tablas(ir(app, "Perfiles e integridad")) if "SHA-256 registrado" in t.columns)
    assert len(integ) >= 17 and set(integ["Estado"]) == {"OK"} and all(len(h) == 64 for h in integ["SHA-256 registrado"])
    assert any("17/17 archivos íntegros" in m.value for m in app.sidebar.markdown)


def test_indicadores_solo_mensuales_en_la_vista_principal(app):
    ir(app, "Indicadores")
    assert all(not m.delta for m in app.metric if m.label.endswith("(mensual)"))
    assert any("no son representativos por ser datos sinteticos" in c.value for c in app.caption)


# ================================================================== adaptadores
def test_adaptador_calcula_el_periodo_previo():
    from nexus.pipeline import run
    from nexus.ui.adapt_variaciones import periodo_previo
    res = run(DATA, profiles_dir=ROOT / "profiles")
    assert [periodo_previo(res, p) for p in PERIODOS] == [None, "2026-10", "2026-11"]


CODE = """
import sys
sys.path.insert(0, {root!r})
import streamlit as st
from nexus.pipeline import run
from nexus.ui import {modulo}

@st.cache_resource
def _run():
    return run({data!r}, profiles_dir={prof!r})

{modulo}.render(_run(), {periodo!r})
"""


@pytest.mark.parametrize("modulo", ["adapt_variaciones", "adapt_indicadores"])
@pytest.mark.parametrize("periodo", PERIODOS)
def test_los_adaptadores_llaman_bien_en_todos_los_periodos(modulo, periodo):
    at = AppTest.from_string(CODE.format(root=str(ROOT), modulo=modulo, data=str(DATA), prof=str(ROOT / "profiles"),
                                         periodo=periodo), default_timeout=90).run()
    assert not at.exception, at.exception
    for t in [e.value for e in at.error] + [m.value for m in at.markdown]:
        assert "falló" not in t and "Traceback" not in t


# ================================================================== los originales no cambian
def test_los_archivos_originales_no_cambian_al_usar_toda_la_app(app):
    antes = hashes()
    for p in PERIODOS:
        en_periodo(app, p)
    ir(app, "Simulador")
    app.slider(key="sim_mxn").set_value(10.0).run()
    app.slider(key="sim_gtq").set_value(-10.0).run()
    ir(app, "Trazabilidad")
    next(b for b in app.selectbox if b.label == "Cifra").select("Ingresos por ventas (cuenta 4000)").run()
    assert not app.exception
    for sec in SECCIONES:
        ir(app, sec)
    assert hashes() == antes and len(antes) >= 17
