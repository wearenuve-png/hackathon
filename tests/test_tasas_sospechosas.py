"""Fase 2: una tasa mayor que 0 pero mal escrita (0.5 en vez de 0.05) se marca; no se bloquea ni se corrige."""
import json
from decimal import Decimal

import pytest

from conftest import DATA, KEY, ROOT
from nexus import validation as V
from nexus.pipeline import run
from test_matriz_errores import RATES, make, row

D = Decimal


def con(tmp_path, gtq_oct, gtq_nov, rows=None):
    rates = dict(RATES)
    rates[("GTQ", "2026-10")], rates[("GTQ", "2026-11")] = gtq_oct, gtq_nov
    return make(tmp_path, rows or [row("2026-10", "Ventas", 1000, "GTQ"), row("2026-11", "Ventas", 1000, "GTQ")],
                rates=rates, periods=("2026-10", "2026-11"))[0]


def tas(res):
    return [f for f in res.findings if f.rule_id == "TAS-01"]


def test_0_05_a_0_5_se_marca_y_muestra_el_impacto(tmp_path):
    res = con(tmp_path, "0.05", "0.5")
    f = tas(res)
    assert len(f) == 1 and f[0].period == "2026-11" and f[0].severity == "WARN"
    assert "0.05 a 0.5" in f[0].message and "+900.0%" in f[0].message
    # impacto a mano: 1,000 GTQ x 0.5 = 500 USD con la tasa nueva; x 0.05 = 50 con la del mes anterior: +450
    assert "+450.00 USD" in f[0].impact and "500.00 USD con la tasa nueva" in f[0].impact \
        and "50.00 USD con la del mes anterior" in f[0].impact
    assert "pide" not in f[0].message and "confirme" in f[0].message                    # pide confirmacion humana


def test_no_bloquea_ni_corrige(tmp_path):
    res = con(tmp_path, "0.05", "0.5")
    nov = [r for r in res.records if r.period == "2026-11"][0]
    assert nov.status == "OK" and nov.fx_rate == D("0.5") and nov.amount_usd == D("500")     # se usa tal cual
    assert res.periods["2026-11"].summary["ingresos"] == D("500")
    assert res.periods["2026-11"].provisional                                              # alerta pendiente de revision


def test_0_05_a_0_0525_no_se_marca(tmp_path):
    assert tas(con(tmp_path, "0.05", "0.0525")) == []                                       # +5 %


def test_el_limite_es_el_umbral(tmp_path):
    assert tas(con(tmp_path, "0.1", "0.115")) == []                                         # +15 % exacto: no supera
    otro = tmp_path / "otro"
    otro.mkdir()
    assert len(tas(con(otro, "0.1", "0.1151"))) == 1                                        # +15.1 %


def test_la_primera_tasa_sin_historial_no_se_marca(tmp_path):
    res, _ = make(tmp_path, [row("2026-10", "Ventas", 1000, "GTQ")], rates={("GTQ", "2026-10"): "5",
                  ("USD", "2026-10"): "1", ("MXN", "2026-10"): "0.05"}, periods=("2026-10",))
    assert tas(res) == []                                                                   # 5 es absurdo, pero no hay historial


def test_baja_fuerte_tambien_se_marca(tmp_path):
    f = tas(con(tmp_path, "0.5", "0.05"))
    assert len(f) == 1 and "-90.0%" in f[0].message and "-450.00 USD" in f[0].impact


def test_el_grupo_de_prueba_no_tiene_tasas_sospechosas():
    res = run(DATA, ic_tolerance_usd=KEY["tolerancia_intercompania_usd"])
    assert [f for f in res.findings if f.rule_id == "TAS-01"] == []                         # GTQ +4 %, MXN +5 %


def test_el_umbral_es_configurable(tmp_path):
    res = run(DATA, ic_tolerance_usd=KEY["tolerancia_intercompania_usd"])
    con3 = V.suspicious_rates(res.records, res.config, threshold="0.03")
    assert {(f.period, f.message.split(":")[1].split()[0]) for f in con3} == {("2026-12", "GTQ"), ("2026-12", "MXN")}
    assert V.suspicious_rates(res.records, res.config, threshold="0.15") == []


def test_configuracion_por_defecto_y_valores_invalidos(tmp_path):
    assert V.load_rate_jump() == D("0.15")
    assert "SUPUESTO" in json.loads(V.VALIDATION_CONFIG.read_text(encoding="utf-8"))["_nota"]
    f = tmp_path / "v.json"
    f.write_text(json.dumps({"umbral_cambio_tasa": "20"}), encoding="utf-8")               # 20 en vez de 0.20
    assert V.load_rate_jump(f) == D("0.15")                                                 # invalido: no se usa
    f.write_text(json.dumps({"umbral_cambio_tasa": "0.30"}), encoding="utf-8")
    assert V.load_rate_jump(f) == D("0.30")
    assert V.load_rate_jump(tmp_path / "no_existe.json") == D("0.15")


def test_la_tasa_sospechosa_tiene_ficha(tmp_path):
    from nexus import diagnostico as DG
    ficha = next(f for f in DG.diagnosticar(con(tmp_path, "0.05", "0.5")) if f.tipo == DG.TASA_SOSPECHOSA)
    assert ficha.impacto_usd == D("450") and "probable" in ficha.causa_probable.lower()
    assert "no la corrige ni bloquea" in ficha.accion
