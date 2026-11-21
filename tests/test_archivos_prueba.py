"""Archivos de prueba ampliados: 12 empresas, 11 monedas, 3 años, tres formatos. Todo limpio y reproducible."""
import csv
import hashlib
import importlib.util
from collections import Counter
from decimal import Decimal
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from nexus.pipeline import run
from nexus.ui import carga_auto as CA

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("gen_prueba", ROOT / "scripts" / "generar_archivos_prueba.py")
GEN = importlib.util.module_from_spec(spec)
spec.loader.exec_module(GEN)


@pytest.fixture(scope="module")
def carpeta(tmp_path_factory):
    d = tmp_path_factory.mktemp("amp")
    GEN.main(d)
    return d


@pytest.fixture(scope="module")
def res(carpeta):
    return run(carpeta)


def hashes(d):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(d).iterdir())}


def test_trae_12_empresas_11_monedas_3_anios_y_3_formatos(carpeta):
    assert len(GEN.EMPRESAS) == 12 and len({e[3] for e in GEN.EMPRESAS}) == 11
    assert Counter(Path(e[4]).suffix for e in GEN.EMPRESAS) == {".xlsx": 4, ".csv": 4, ".json": 4}
    assert {p[:4] for p in GEN.PERIODOS} == {"2025", "2026", "2027"} and len(GEN.PERIODOS) == 27
    assert len(list(carpeta.iterdir())) == 12 + 5                                       # 12 presupuestos + 5 tablas


def test_el_motor_lo_lee_completo_sin_un_solo_hallazgo_y_cada_mes_cuadra(res):
    assert len(res.records) == 12 * 27 * 18 and not res.findings                       # 5,832 registros, ningun error
    assert all(r.status in ("MATCHED", "AUTO") for r in res.load_reports.values())
    for p, pr in res.periods.items():
        assert not pr.provisional and pr.summary["activo_menos_pasivo_y_patrimonio"] == 0, p


def test_los_ingresos_de_una_empresa_coinciden_con_el_calculo_independiente(carpeta, res):
    """EMP102 (CSV con coma decimal, COP): lo leido x la tasa del mes, calculado aqui a mano, es lo que consolida."""
    tasas = {(r["periodo"], r["moneda"]): Decimal(r["usd_por_unidad_local"])
             for r in csv.DictReader(open(carpeta / "tasas.csv", encoding="utf-8"))}
    esperado = {}
    for r in csv.DictReader(open(carpeta / "ferrex_colombia.csv", encoding="utf-8"), delimiter=";"):
        if r["cuenta"] == "Ingresos por ventas netas":
            m, y = r["periodo"].split("/")
            esperado[f"{y}-{m}"] = Decimal(r["importe"].replace(".", "").replace(",", ".")) * tasas[(f"{y}-{m}", "COP")]
    assert len(esperado) == 27
    for p, usd in esperado.items():
        real = sum((x.amount_usd for x in res.records if x.company_id == "EMP102" and x.period == p
                    and x.account_code == "4000"), Decimal(0))
        assert real == usd, p


def test_es_reproducible_y_se_puede_cargar_con_el_boton(carpeta, tmp_path):
    GEN.main(tmp_path / "otra")
    otra = tmp_path / "otra"
    for f in carpeta.iterdir():
        if f.suffix == ".xlsx":                                                          # el zip guarda la hora: se compara el contenido
            from openpyxl import load_workbook
            filas = lambda d: [[c.value for c in r] for r in load_workbook(d / f.name).active.iter_rows()]
            assert filas(otra) == filas(carpeta), f.name
        else:
            assert (otra / f.name).read_bytes() == f.read_bytes(), f.name               # semilla fija: mismos bytes
    r = CA.preparar([str(carpeta)])
    assert r["ok"] and not r["problemas"] and len(r["usados"]) == 12 and not r["sin_usar"]


def test_en_la_app_se_ven_los_tres_anios_sin_errores(carpeta, monkeypatch):
    monkeypatch.setenv("NEXUS_TEST_SIN_CARGA", "1")
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180).run()
    at.session_state["carga"] = CA.preparar([str(carpeta)])
    at.run()
    assert not at.exception, at.exception
    assert len(at.sidebar.radio[0].options) == 27 and at.sidebar.radio[0].options[0].startswith("2025-01")
    for sec in ("Inicio", "Estados financieros", "Hallazgos", "Variaciones", "Indicadores", "Trazabilidad", "Ayuda"):
        at.radio(key="nav").set_value(sec).run()
        assert not at.exception, (sec, at.exception)
        assert "falló" not in " ".join(m.value for m in at.markdown)


def test_la_carpeta_lista_del_repositorio_es_la_que_genera_el_script(carpeta):
    listo = ROOT / "data" / "demo_ampliado"
    assert sorted(p.name for p in listo.iterdir()) == sorted(p.name for p in carpeta.iterdir())
    for f in carpeta.iterdir():
        if f.suffix != ".xlsx":
            assert (listo / f.name).read_bytes() == f.read_bytes(), f.name
    assert CA.preparar([str(listo)])["ok"]
