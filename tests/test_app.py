"""Prueba real de la interfaz Streamlit (streamlit.testing.v1.AppTest, sin navegador).
La app solo muestra lo que devuelve el motor: se comprueba contra tests/fixtures/answer_key.json."""
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from conftest import KEY

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def fmt(s):
    return f"{Decimal(s).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):,.2f}"


def frames(at):
    return [d.value for d in at.dataframe]


def text_of(at):
    out = [m.value for m in at.markdown] + [m.value for m in at.error] + [m.value for m in at.success]
    out += [str(f.to_dict("records")) for f in frames(at)]
    return "\n".join(out)


@pytest.fixture()
def at():
    a = AppTest.from_file(APP, default_timeout=90).run()
    assert not a.exception, a.exception
    return a


def test_arranca_sin_errores_y_con_las_pestanas_del_rediseno(at):
    # las 8 pestanas del rediseno de feat/ui + Simulador y Ayuda (Hallazgos vive dentro de "Alertas y errores")
    assert [t.label for t in at.tabs] == ["Resumen", "Estados financieros", "Alertas y errores", "Intercompañía",
                                          "Trazabilidad", "Indicadores", "Variaciones", "Simulador",
                                          "Perfiles e integridad", "Ayuda", "Asistente"]
    assert list(at.sidebar.radio[0].options) == ["2026-10 (real)", "2026-11 (real)", "2026-12 (presupuesto)"]


@pytest.mark.parametrize("periodo", list(KEY["consolidado_esperado_usd"]))
def test_cada_periodo_muestra_la_cifra_de_la_clave_y_la_etiqueta(at, periodo):
    at.sidebar.radio[0].set_value(periodo).run()
    assert not at.exception
    exp = KEY["consolidado_esperado_usd"][periodo]["resumen"]
    estado = next(f for f in frames(at) if "Concepto" in f.columns and "Consolidado" in f.columns
                  and "Ingresos" in set(f["Concepto"]))
    row = estado[estado["Concepto"] == "Ingresos"].iloc[0]
    assert row["Consolidado"] == fmt(exp["ingresos"])
    assert estado[estado["Concepto"] == "= Utilidad neta"].iloc[0]["Consolidado"] == fmt(exp["utilidad_neta"])
    assert any(e.value == "PROVISIONAL" for e in at.error)            # los tres periodos son provisionales


def test_octubre_muestra_rango_de_impacto_y_exclusiones(at):
    assert "Rango posible de utilidad neta" in text_of(at)
    full = text_of(at)
    assert "BLOCKED" in full and "PENDING_MAPPING" in full and "EXCLUDED_DUPLICATE" in full


def test_la_discrepancia_se_muestra_en_una_sola_fila(at):
    at.sidebar.radio[0].set_value("2026-11").run()
    assert not at.exception
    ic = next(f for f in frames(at) if "Afecta" in f.columns)
    assert len(ic) == 1                                                           # no dos (operacion y saldo)
    fila = ic.iloc[0]
    assert fila["Afecta"] == "operación (venta) y saldo (CxC y CxP)" and fila["Diferencia"] == "2,000.00"
    assert any("una sola vez" in c.value for c in at.caption)


def test_noviembre_muestra_la_discrepancia_intercompania(at):
    at.sidebar.radio[0].set_value("2026-11").run()
    disc = KEY["discrepancias_esperadas"][0]
    full = text_of(at)
    assert disc["reference"] in full and fmt(disc["difference_usd"]) in full


def test_trazabilidad_llega_a_archivo_hoja_y_fila(at):
    next(b for b in at.selectbox if b.label == "Cifra").select("Ingresos por ventas (cuenta 4000)").run()
    assert not at.exception
    t = next(f for f in frames(at) if "Archivo" in f.columns and "Fila" in f.columns and "Tasa" in f.columns)
    assert len(t) > 0 and (t["Archivo"] != "").all() and (t["Fila"] > 0).all()
    assert set(t.columns) >= {"Hoja", "Importe original", "Moneda", "Tasa", "Importe USD"}
    assert t["Archivo"].str.endswith((".xlsx", ".csv", ".json")).all()


def test_perfiles_muestran_estado_de_la_ultima_carga(at):
    perf = next(f for f in frames(at) if "Ultima carga" in f.columns)
    assert len(perf) == 6 and set(perf["Ultima carga"]) == {"Coincide con el perfil"}
    assert set(perf["Formato"]) == {"XLSX", "CSV", "JSON"}
    assert {"Version", "Aprobado por"} <= set(perf.columns)


def test_sin_carpeta_de_perfiles_usa_deteccion_automatica(at):
    at.sidebar.text_input[1].set_value("").run()
    assert not at.exception
    perf = next(f for f in frames(at) if "Ultima carga" in f.columns)
    assert set(perf["Ultima carga"]) == {"Sin perfil (auto)"}


def test_muestra_la_fuente_y_la_integridad_de_los_archivos(at):
    assert any("Fuente: carpeta del servidor" in e.value for e in at.success)
    integ = next(f for f in frames(at) if "SHA-256 registrado" in f.columns)
    assert len(integ) >= 6 + 5 and set(integ["Estado"]) == {"OK"}               # empresas + tablas + perfiles
    assert all(len(h) == 64 for h in integ["SHA-256 registrado"])
    assert not at.sidebar.get("file_uploader")                                   # sin subida manual
