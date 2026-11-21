"""ROIC, ROCE y EVA: calculos a mano y contra answer_key.json (independiente del motor)."""
import json
from decimal import Decimal

import pytest

from conftest import DATA, KEY
from nexus import metrics, validation
from nexus.metrics import IndicatorParams, compute_indicators, load_params
from nexus.pipeline import run
from nexus.schemas import BLOCK, WARN

D = Decimal


@pytest.fixture(scope="module")
def res():
    return run(DATA, ic_tolerance_usd=KEY["tolerancia_intercompania_usd"])


# ---------------------------------------------------------------- a mano (ejemplo del brief)
def test_ejemplo_del_brief_roic_y_eva():
    nopat = metrics.nopat(D("80000"), D("0.50"))                    # 80,000 x (1 - 0.5) = 40,000
    assert nopat == D("40000")
    assert metrics.roic(nopat, D("400000")) == D("0.1")             # 40,000 / 400,000 = 10%
    assert metrics.eva(nopat, D("0.08"), D("400000")) == D("8000")  # 40,000 - 0.08 x 400,000 = 8,000


def test_roce_a_mano():
    assert metrics.roce(D("50000"), D("500000")) == D("0.1")        # 50,000 / 500,000 = 10%


def test_capital_no_positivo_no_divide():
    for cap in (D("0"), D("-1")):
        with pytest.raises(ValueError):
            metrics.roic(D("1"), cap)
        with pytest.raises(ValueError):
            metrics.roce(D("1"), cap)


# ---------------------------------------------------------------- contra la clave (calculo independiente)
def esperado(periodo, params):
    k = KEY["consolidado_esperado_usd"][periodo]
    cta, rs = {c: D(v) for c, v in k["por_cuenta"].items()}, {c: D(v) for c, v in k["resumen"].items()}
    ebit = rs["ebit"]
    ci = cta["2500"] + rs["patrimonio"] - cta["1000"]                 # deuda + patrimonio - caja
    ce = rs["activo_total"] - (cta["2000"] + cta["2100"])             # activo total - pasivo corriente
    nopat = ebit * (1 - params.tax_rate)
    n = params.periods_per_year
    return dict(ebit=ebit, nopat=nopat, ci=ci, ce=ce, roic=nopat / ci, roce=ebit / ce,
                eva=nopat - params.wacc / n * ci, roic_a=nopat / ci * n, roce_a=ebit / ce * n)


@pytest.mark.parametrize("periodo", list(KEY["consolidado_esperado_usd"]))
@pytest.mark.parametrize("params", [IndicatorParams(),
                                    IndicatorParams(wacc=D("0.10"), tax_rate=D("0.30"), periods_per_year=1)])
def test_indicadores_coinciden_con_el_calculo_independiente(res, periodo, params):
    r = compute_indicators(res, periodo, params)
    e = esperado(periodo, params)
    assert not r.blocked and r.findings == []
    tol = D("0.01")                       # la clave redondea a 2 decimales
    assert abs(r.ebit - e["ebit"]) <= tol and abs(r.nopat - e["nopat"]) <= tol
    assert abs(r.invested_capital - e["ci"]) <= D("0.05") and abs(r.capital_employed - e["ce"]) <= D("0.05")
    assert abs(r.roic - e["roic"]) < D("0.000001") and abs(r.roce - e["roce"]) < D("0.000001")
    assert abs(r.roic_annualized - e["roic_a"]) < D("0.00001") and abs(r.roce_annualized - e["roce_a"]) < D("0.00001")
    assert abs(r.eva - e["eva"]) <= D("0.05")


def test_octubre_a_mano(res):
    """Octubre: EBIT 433,300; NOPAT = 433,300 x 0.75 = 324,975. Capital invertido = deuda 1,035,000 +
    patrimonio 2,297,500 - caja 419,250 = 2,913,250. ROIC = 324,975 / 2,913,250 = 11.16%."""
    r = compute_indicators(res, "2026-10", IndicatorParams())
    assert r.nopat.quantize(D("0.01")) == D("324975.00")
    assert r.invested_capital.quantize(D("0.01")) == D("2913250.00")
    assert f"{r.roic:.2%}" == "11.16%"
    assert r.eva.quantize(D("0.01")) == (D("324975") - D("0.08") / 12 * D("2913250")).quantize(D("0.01"))


def test_las_entradas_estan_etiquetadas_con_su_origen(res):
    r = compute_indicators(res, "2026-10", IndicatorParams())
    origen = {i.name: i.source for i in r.inputs}
    assert origen["WACC (anual)"] == "SUPUESTO" and origen["Tasa de impuesto"] == "SUPUESTO"
    assert origen["Capital invertido"] == "CONSOLIDADO" and origen["EBIT del periodo"] == "CONSOLIDADO"
    r2 = compute_indicators(res, "2026-10", IndicatorParams(invested_capital_override=D("1000000")))
    assert {i.name: i.source for i in r2.inputs}["Capital invertido"] == "SUPUESTO"
    assert r2.roic == r2.nopat / D("1000000")


def test_los_indicadores_heredan_provisional(res):
    for p in res.periods:
        assert compute_indicators(res, p).provisional == res.periods[p].provisional is True


def test_no_modifica_el_consolidado(res):
    antes = {p: dict(pr.summary) for p, pr in res.periods.items()}
    for p in res.periods:
        compute_indicators(res, p, IndicatorParams(wacc=D("8")))
    assert {p: pr.summary for p, pr in res.periods.items()} == antes


# ---------------------------------------------------------------- el validador revisa las entradas
@pytest.mark.parametrize("override,rule", [(D("0"), "IND-01"), (D("-5"), "IND-01")])
def test_capital_invertido_no_positivo_bloquea_roic_y_eva(res, override, rule):
    r = compute_indicators(res, "2026-10", IndicatorParams(invested_capital_override=override))
    assert rule in {f.rule_id for f in r.findings if f.severity == BLOCK}
    assert r.roic is None and r.eva is None and r.roce is not None


def test_capital_empleado_no_positivo_bloquea_roce(res):
    r = compute_indicators(res, "2026-10", IndicatorParams(capital_employed_override=D("-1")))
    assert "IND-02" in {f.rule_id for f in r.findings} and r.roce is None and r.roic is not None


def test_wacc_escrito_como_porcentaje_se_bloquea(res):
    r = compute_indicators(res, "2026-10", IndicatorParams(wacc=D("8")))        # 8 en vez de 0.08
    assert any(f.rule_id == "IND-03" and f.severity == BLOCK for f in r.findings)
    assert r.eva is None and r.roic is not None


def test_tasa_de_impuesto_fuera_de_rango_bloquea_nopat(res):
    r = compute_indicators(res, "2026-10", IndicatorParams(tax_rate=D("25")))
    assert any(f.rule_id == "IND-04" and f.severity == BLOCK for f in r.findings)
    assert r.nopat is None and r.roic is None and r.eva is None and r.roce is not None


def test_valores_inusuales_avisan_pero_calculan(res):
    r = compute_indicators(res, "2026-10", IndicatorParams(wacc=D("0.35"), tax_rate=D("0.45")))
    assert {f.rule_id for f in r.findings} == {"IND-03", "IND-04"}
    assert all(f.severity == WARN for f in r.findings) and r.eva is not None


def test_periodos_por_anio_invalido(res):
    r = compute_indicators(res, "2026-10", IndicatorParams(periods_per_year=5))
    assert any(f.rule_id == "IND-05" for f in r.findings) and r.roic_annualized is None and r.eva is None


def test_ebit_negativo_avisa():
    fs = metrics.validate_inputs(IndicatorParams(), D("-1"), D("10"), D("10"))
    assert [f.rule_id for f in fs] == ["IND-06"] and fs[0].severity == WARN


def test_el_validador_expone_la_comprobacion():
    a = validation.validate_indicator_inputs(IndicatorParams(wacc=D("8")), D("1"), D("1"), D("1"), "2026-10")
    b = metrics.validate_inputs(IndicatorParams(wacc=D("8")), D("1"), D("1"), D("1"), "2026-10")
    assert [f.rule_id for f in a] == [f.rule_id for f in b] == ["IND-03"]


# ---------------------------------------------------------------- parametros configurables
def test_parametros_por_defecto_vienen_de_config_y_son_supuestos():
    p = load_params()
    assert (p.wacc, p.tax_rate, p.periods_per_year) == (D("0.08"), D("0.25"), 12)
    assert "SUPUESTO" in json.loads(metrics.DEFAULT_CONFIG.read_text(encoding="utf-8"))["_nota"]


def test_parametros_se_cambian_sin_tocar_el_codigo(tmp_path):
    f = tmp_path / "ind.json"
    f.write_text(json.dumps({"wacc": "0.12", "tax_rate": "0.30", "periods_per_year": 4,
                             "invested_capital_override": "500000"}), encoding="utf-8")
    p = load_params(f)
    assert (p.wacc, p.tax_rate, p.periods_per_year, p.invested_capital_override) == \
        (D("0.12"), D("0.30"), 4, D("500000"))
