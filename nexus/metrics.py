"""ROIC, ROCE y EVA calculados desde el consolidado. Python calcula; no hay IA.

Formulas (PDF del brief):
    NOPAT = EBIT x (1 - tasa de impuesto)
    ROIC  = NOPAT / capital invertido
    ROCE  = EBIT / capital empleado
    EVA   = NOPAT - (WACC x capital invertido)

Definiciones usadas (SUPUESTOS, configurables en config/indicators.json):
    capital invertido = deuda + patrimonio - caja
        deuda = cuentas de pasivo NO corriente del catalogo; caja = cash_account_codes
    capital empleado  = activo total - pasivo corriente
    WACC y tasa de impuesto son parametros del equipo, no datos del consolidado.
    Los resultados son del PERIODO (un mes). El WACC es anual: en el EVA se usa WACC / periodos_por_anio.
    ROIC y ROCE tambien se muestran anualizados (x periodos_por_anio). El capital es el del cierre del periodo
    (no un promedio): simplificacion declarada.
Dinero con Decimal. Una entrada invalida bloquea el indicador (None) y deja un hallazgo; nunca se calcula
con una entrada dudosa.
"""
import json
from dataclasses import dataclass, field, replace
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .schemas import BLOCK, WARN, Finding

CONSOLIDADO, SUPUESTO = "CONSOLIDADO", "SUPUESTO"
DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config" / "indicators.json"


# ------------------------------------------------------------------ formulas puras
def nopat(ebit: Decimal, tax_rate: Decimal) -> Decimal:
    return ebit * (1 - tax_rate)


def roic(nopat_: Decimal, invested_capital: Decimal) -> Decimal:
    if invested_capital <= 0:
        raise ValueError("El capital invertido debe ser positivo")
    return nopat_ / invested_capital


def roce(ebit: Decimal, capital_employed: Decimal) -> Decimal:
    if capital_employed <= 0:
        raise ValueError("El capital empleado debe ser positivo")
    return ebit / capital_employed


def eva(nopat_: Decimal, wacc: Decimal, invested_capital: Decimal) -> Decimal:
    return nopat_ - wacc * invested_capital


# ------------------------------------------------------------------ parametros
@dataclass
class IndicatorParams:
    wacc: Decimal = Decimal("0.08")                  # SUPUESTO, anual
    tax_rate: Decimal = Decimal("0.25")              # SUPUESTO
    periods_per_year: int = 12                       # 12 = datos mensuales
    cash_account_codes: Tuple[str, ...] = ("1000",)  # SUPUESTO: cuentas de caja
    invested_capital_override: Optional[Decimal] = None
    capital_employed_override: Optional[Decimal] = None


def _dec(v):
    return None if v is None else Decimal(str(v))


def load_params(path=None) -> IndicatorParams:
    p = Path(path) if path else DEFAULT_CONFIG
    if not p.exists():
        return IndicatorParams()
    d = json.loads(p.read_text(encoding="utf-8"))
    return IndicatorParams(
        wacc=Decimal(str(d.get("wacc", "0.08"))), tax_rate=Decimal(str(d.get("tax_rate", "0.25"))),
        periods_per_year=int(d.get("periods_per_year", 12)),
        cash_account_codes=tuple(d.get("cash_account_codes", ["1000"])),
        invested_capital_override=_dec(d.get("invested_capital_override")),
        capital_employed_override=_dec(d.get("capital_employed_override")))


# ------------------------------------------------------------------ resultado
@dataclass
class InputLine:
    name: str
    value: Optional[Decimal]
    source: str                      # CONSOLIDADO o SUPUESTO
    note: str = ""


@dataclass
class IndicatorResult:
    period: str
    provisional: bool
    params: IndicatorParams
    inputs: List[InputLine]
    ebit: Decimal
    nopat: Optional[Decimal]
    invested_capital: Optional[Decimal]
    capital_employed: Optional[Decimal]
    roic: Optional[Decimal] = None
    roce: Optional[Decimal] = None
    eva: Optional[Decimal] = None
    roic_annualized: Optional[Decimal] = None
    roce_annualized: Optional[Decimal] = None
    findings: List[Finding] = field(default_factory=list)
    formulas: Dict[str, str] = field(default_factory=dict)

    @property
    def blocked(self) -> bool:
        return any(f.severity == BLOCK for f in self.findings)


FORMULAS = {
    "NOPAT": "NOPAT = EBIT x (1 - tasa de impuesto)",
    "ROIC": "ROIC = NOPAT / capital invertido",
    "ROCE": "ROCE = EBIT / capital empleado",
    "EVA": "EVA = NOPAT - (WACC / periodos por anio) x capital invertido",
    "CI": "Capital invertido = deuda + patrimonio - caja",
    "CE": "Capital empleado = activo total - pasivo corriente",
}


# ------------------------------------------------------------------ validacion de entradas
def validate_inputs(params: IndicatorParams, ebit: Optional[Decimal], invested_capital: Optional[Decimal],
                    capital_employed: Optional[Decimal], period: Optional[str] = None) -> List[Finding]:
    """Ninguna entrada dudosa pasa inadvertida. BLOCK = el indicador no se calcula; WARN = se calcula y se avisa."""
    out: List[Finding] = []

    def add(rule, sev, msg, found, expected, sug):
        out.append(Finding(f"F-{rule}-{len(out) + 1:02d}", rule, sev, msg, [], period, None, str(found),
                           str(expected), sug))

    if invested_capital is None or invested_capital <= 0:
        add("IND-01", BLOCK, "Capital invertido no positivo: ROIC y EVA no se calculan", invested_capital, "> 0",
            "Revisar deuda, patrimonio y caja del consolidado, o el supuesto de capital")
    if capital_employed is None or capital_employed <= 0:
        add("IND-02", BLOCK, "Capital empleado no positivo: ROCE no se calcula", capital_employed, "> 0",
            "Revisar activo total y pasivo corriente del consolidado")
    if not (0 < params.wacc <= 1):
        add("IND-03", BLOCK, f"WACC fuera de rango ({params.wacc}): debe ser una fraccion entre 0 y 1 (8% = 0.08)",
            params.wacc, "0 < WACC <= 1", "Corregir el supuesto de WACC")
    elif params.wacc > Decimal("0.30"):
        add("IND-03", WARN, f"WACC inusualmente alto ({params.wacc:.1%})", params.wacc, "<= 30%",
            "Confirmar el supuesto")
    if not (0 <= params.tax_rate < 1):
        add("IND-04", BLOCK, f"Tasa de impuesto fuera de rango ({params.tax_rate}): debe ser una fraccion "
            f"entre 0 y 1 (25% = 0.25)", params.tax_rate, "0 <= t < 1", "Corregir el supuesto de impuesto")
    elif params.tax_rate > Decimal("0.40"):
        add("IND-04", WARN, f"Tasa de impuesto inusualmente alta ({params.tax_rate:.1%})", params.tax_rate,
            "<= 40%", "Confirmar el supuesto")
    if params.periods_per_year not in (1, 2, 4, 12):
        add("IND-05", BLOCK, f"Periodos por anio invalido: {params.periods_per_year}", params.periods_per_year,
            "1, 2, 4 o 12", "Usar 12 para datos mensuales")
    if ebit is not None and ebit < 0:
        add("IND-06", WARN, "EBIT negativo: NOPAT, ROIC y ROCE saldran negativos", ebit, ">= 0",
            "Revisar el resultado del periodo")
    return out


# ------------------------------------------------------------------ calculo desde el consolidado
def compute_indicators(consolidado, period: str, params: Optional[IndicatorParams] = None) -> IndicatorResult:
    """consolidado: RunResult del motor (nexus.pipeline.run). Lee solo cifras ya consolidadas en USD."""
    params = params or load_params()
    pr = consolidado.periods[period]
    cat = consolidado.config.catalog
    lines = pr.lines
    s = pr.summary

    ebit = s["ebit"]
    debt = sum((l.amount_usd for c, l in lines.items() if cat[c].cls == "pasivo" and cat[c].current is False),
               Decimal(0))
    cash = sum((lines[c].amount_usd for c in params.cash_account_codes if c in lines), Decimal(0))
    current_liab = sum((l.amount_usd for c, l in lines.items() if cat[c].cls == "pasivo" and cat[c].current is True),
                       Decimal(0))
    equity, assets = s["patrimonio"], s["activo_total"]

    inputs = [
        InputLine("EBIT del periodo", ebit, CONSOLIDADO, "Ingresos - costo de ventas - gastos operativos"),
        InputLine("Patrimonio", equity, CONSOLIDADO),
        InputLine("Deuda (pasivo no corriente)", debt, CONSOLIDADO, "Cuentas de pasivo no corriente del catalogo"),
        InputLine("Caja", cash, CONSOLIDADO, "Cuentas: " + ", ".join(params.cash_account_codes) + " (SUPUESTO)"),
        InputLine("Activo total", assets, CONSOLIDADO),
        InputLine("Pasivo corriente", current_liab, CONSOLIDADO),
    ]
    ci_calc, ce_calc = debt + equity - cash, assets - current_liab
    ci = params.invested_capital_override if params.invested_capital_override is not None else ci_calc
    ce = params.capital_employed_override if params.capital_employed_override is not None else ce_calc
    inputs.append(InputLine("Capital invertido", ci, SUPUESTO if params.invested_capital_override is not None
                            else CONSOLIDADO, "Valor fijado por el equipo" if params.invested_capital_override
                            is not None else "Deuda + patrimonio - caja (definicion SUPUESTA)"))
    inputs.append(InputLine("Capital empleado", ce, SUPUESTO if params.capital_employed_override is not None
                            else CONSOLIDADO, "Valor fijado por el equipo" if params.capital_employed_override
                            is not None else "Activo total - pasivo corriente (definicion SUPUESTA)"))
    inputs.append(InputLine("Tasa de impuesto", params.tax_rate, SUPUESTO, "No es el impuesto contable del consolidado"))
    inputs.append(InputLine("WACC (anual)", params.wacc, SUPUESTO))
    inputs.append(InputLine("Periodos por anio", Decimal(params.periods_per_year), SUPUESTO,
                            "12 = datos mensuales"))

    res = IndicatorResult(period, pr.provisional, params, inputs, ebit, None, ci, ce, formulas=dict(FORMULAS))
    res.findings = validate_inputs(params, ebit, ci, ce, period)
    blocked = {f.rule_id for f in res.findings if f.severity == BLOCK}
    tax_ok = "IND-04" not in blocked
    ppy_ok = "IND-05" not in blocked
    wacc_ok = "IND-03" not in blocked
    n = nopat(ebit, params.tax_rate) if tax_ok else None
    res.nopat = n
    if n is not None and "IND-01" not in blocked:
        res.roic = roic(n, ci)
        if ppy_ok:
            res.roic_annualized = res.roic * params.periods_per_year
            if wacc_ok:
                res.eva = eva(n, params.wacc / params.periods_per_year, ci)
    if "IND-02" not in blocked:
        res.roce = roce(ebit, ce)
        if ppy_ok:
            res.roce_annualized = res.roce * params.periods_per_year
    return res
