"""Prueba real de la interfaz Streamlit (streamlit.testing.v1.AppTest, sin navegador).
La app solo muestra lo que devuelve el motor: se comprueba contra tests/fixtures/answer_key.json.
Las secciones se eligen en el menu horizontal de arriba (key "nav")."""
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from conftest import KEY

APP = str(Path(__file__).resolve().parent.parent / "app.py")
SECCIONES = ["Inicio", "Estados financieros", "Alertas y errores", "Hallazgos", "Intercompañía", "Trazabilidad",
             "Indicadores", "Variaciones", "Simulador", "Perfiles e integridad", "Ayuda"]


def fmt(s):
    return f"{Decimal(s).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):,.2f}"


def frames(at):
    return [d.value for d in at.dataframe]


def text_of(at):
    out = [m.value for m in at.markdown] + [m.value for m in at.error] + [m.value for m in at.success]
    out += [str(f.to_dict("records")) for f in frames(at)]
    return "\n".join(out)


def ir(at, seccion):
    at.radio(key="nav").set_value(seccion).run()
    assert not at.exception, at.exception
    return at


@pytest.fixture()
def at():
    a = AppTest.from_file(APP, default_timeout=90).run()
    assert not a.exception, a.exception
    return a


def test_arranca_sin_errores_con_el_menu_horizontal(at):
    nav = at.radio(key="nav")
    assert nav.value == "Inicio"
    assert len(nav.options) == len(SECCIONES) and nav.options[0] == ":material/home: Inicio"   # icono de inicio
    assert len(at.tabs) == 0 and not at.sidebar.selectbox                         # sin pestanas ni desplegable
    assert list(at.sidebar.radio[0].options) == ["2026-10 (real)", "2026-11 (real)", "2026-12 (presupuesto)"]


@pytest.mark.parametrize("seccion", SECCIONES)
def test_cada_seccion_abre_sin_errores(at, seccion):
    ir(at, seccion)


@pytest.mark.parametrize("periodo", list(KEY["consolidado_esperado_usd"]))
def test_cada_periodo_muestra_la_cifra_de_la_clave_y_la_etiqueta(at, periodo):
    at.sidebar.radio[0].set_value(periodo).run()
    ir(at, "Estados financieros")
    exp = KEY["consolidado_esperado_usd"][periodo]["resumen"]
    estado = next(f for f in frames(at) if "Concepto" in f.columns and "Consolidado" in f.columns
                  and "Ingresos" in set(f["Concepto"]))
    row = estado[estado["Concepto"] == "Ingresos"].iloc[0]
    assert row["Consolidado"] == fmt(exp["ingresos"])
    assert estado[estado["Concepto"] == "= Utilidad neta"].iloc[0]["Consolidado"] == fmt(exp["utilidad_neta"])
    assert any(e.value == "PROVISIONAL" for e in at.error)            # los tres periodos son provisionales


def test_octubre_muestra_rango_de_impacto_y_exclusiones(at):
    assert "Rango posible de utilidad neta" in text_of(at)                       # Inicio
    full = text_of(ir(at, "Alertas y errores"))
    assert "BLOCKED" in full and "PENDING_MAPPING" in full and "EXCLUDED_DUPLICATE" in full


def test_la_discrepancia_se_muestra_en_una_sola_fila(at):
    at.sidebar.radio[0].set_value("2026-11").run()
    ir(at, "Intercompañía")
    ic = next(f for f in frames(at) if "Afecta" in f.columns)
    assert len(ic) == 1                                                           # no dos (operacion y saldo)
    fila = ic.iloc[0]
    assert fila["Afecta"] == "operacion (venta) y saldo (CxC y CxP)" and fila["Diferencia"] == "2,000.00"
    assert any("una sola vez" in c.value for c in at.caption)


def test_noviembre_muestra_la_discrepancia_intercompania(at):
    at.sidebar.radio[0].set_value("2026-11").run()
    disc = KEY["discrepancias_esperadas"][0]
    full = text_of(ir(at, "Intercompañía"))
    assert disc["reference"] in full and fmt(disc["difference_usd"]) in full


def test_trazabilidad_llega_a_archivo_hoja_y_fila(at):
    ir(at, "Trazabilidad")
    at.selectbox(key="traza_cifra").select("4000 - Ingresos por ventas").run()
    assert not at.exception
    t = next(f for f in frames(at) if "Archivo" in f.columns and "Fila" in f.columns and "Tasa" in f.columns)
    assert len(t) > 0 and (t["Archivo"] != "").all() and (t["Fila"] > 0).all()
    assert set(t.columns) >= {"Hoja", "Importe original", "Moneda", "Tasa", "Importe USD"}
    assert t["Archivo"].str.endswith((".xlsx", ".csv", ".json")).all()


def test_perfiles_muestran_estado_de_la_ultima_carga(at):
    perf = next(f for f in frames(ir(at, "Perfiles e integridad")) if "Ultima carga" in f.columns)
    assert len(perf) == 6 and set(perf["Ultima carga"]) == {"Coincide con el perfil"}
    assert set(perf["Formato"]) == {"XLSX", "CSV", "JSON"}
    assert {"Version", "Aprobado por"} <= set(perf.columns)


def test_sin_carpeta_de_perfiles_usa_deteccion_automatica(at):
    at.sidebar.text_input[1].set_value("").run()
    assert not at.exception
    perf = next(f for f in frames(ir(at, "Perfiles e integridad")) if "Ultima carga" in f.columns)
    assert set(perf["Ultima carga"]) == {"Sin perfil (auto)"}


def test_muestra_la_fuente_y_la_integridad_de_los_archivos(at):
    assert any("Fuente: carpeta del servidor" in e.value for e in at.success)
    integ = next(f for f in frames(ir(at, "Perfiles e integridad")) if "SHA-256 registrado" in f.columns)
    assert len(integ) >= 6 + 5 and set(integ["Estado"]) == {"OK"}               # empresas + tablas + perfiles
    assert all(len(h) == 64 for h in integ["SHA-256 registrado"])
    assert not at.sidebar.get("file_uploader")                                   # sin subida manual


def test_modo_claro_cambia_el_tema_y_vuelve_al_oscuro(at):
    from streamlit import config as st_config
    try:
        at.sidebar.toggle(key="modo_claro").set_value(True).run()
        assert not at.exception, at.exception
        assert st_config.get_option("theme.base") == "light"
        assert st_config.get_option("theme.textColor") == "#141312"                # letras negras en claro
        at.sidebar.toggle(key="modo_claro").set_value(False).run()
        assert not at.exception, at.exception
        assert st_config.get_option("theme.base") == "dark"
        assert st_config.get_option("theme.textColor") == "#F5F3EF"                # letras blancas en oscuro
    finally:
        st_config.set_option("theme.base", "dark")


def test_colores_por_empresa_un_tono_distinto_aunque_sean_del_mismo_pais():
    from types import SimpleNamespace as E
    from nexus.ui.colores import COUNTRY_COLORS, company_colors
    emp = {"A": E(country="Guatemala"), "B": E(country="Guatemala"), "C": E(country="México"),
           "D": E(country="El Salvador"), "E": E(country="México"), "F": E(country="Panama"), "G": E(country="Chile")}
    for modo in ("dark", "light"):
        c = company_colors(emp, modo)
        assert len(set(c.values())) == len(emp)                                      # todas distintas
        assert {c["C"], c["E"]} == set(COUNTRY_COLORS[modo]["mexico"])               # Mexico: dos verdes
        assert c["D"] in COUNTRY_COLORS[modo]["el salvador"]                          # El Salvador: azul
