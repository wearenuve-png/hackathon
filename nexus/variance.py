"""Explicador de variaciones con plantillas (sin IA): compara dos periodos y descompone cada variacion en causas
que SUMAN EXACTO el total. Todo es calculo de Decimal sobre el consolidado del motor.

Para cada celda (empresa x cuenta) la variacion del consolidado, en USD, es:

    total = Operacion + Tipo de cambio + Eliminaciones intercompania + Ajustes y registros fuera + Mes faltante
            + Sin explicar

    Operacion        = (local_nuevo - local_previo) x tasa_previa          (por moneda)
    Tipo de cambio   = local_nuevo x (tasa_nueva - tasa_previa)
    Eliminaciones    = cambio en las eliminaciones intercompania aplicadas (ajustes IC_ELIMINATION)
    Ajustes/fuera    = efecto de los duplicados excluidos con ajuste y de los registros BLOQUEADOS que si se
                       pueden valorar en USD (no entran al consolidado)
    Mes faltante     = movimiento de una empresa que no entrego uno de los dos periodos
    Sin explicar     = lo que queda: p. ej. registros bloqueados sin valor en USD (moneda invalida), cambio de
                       moneda entre periodos o tasa faltante. NUNCA se reparte a ciegas.

La convencion Operacion/Tipo de cambio es un SUPUESTO metodologico (valorar el movimiento a la tasa previa).
"""
import json
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .consolidation import UTILITY_SIGN
from .currency import to_usd
from .schemas import BLOCK, BLOCKED, EXCLUDED_DUPLICATE, OK, TOTAL, WARN, Finding

D0 = Decimal(0)
DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config" / "variance.json"
OP, FX, ELIM, AJ, MES, SIN = "OPERACION", "TIPO_CAMBIO", "ELIMINACIONES", "AJUSTES_FUERA", "MES_FALTANTE", "SIN_EXPLICAR"
CAUSES = [OP, FX, ELIM, AJ, MES, SIN]
CAUSE_NAMES = {OP: "Operación", FX: "Tipo de cambio", ELIM: "Cambio en eliminaciones intercompañía",
               AJ: "Ajustes registrados y registros bloqueados o pendientes", MES: "Mes faltante de una empresa",
               SIN: "Sin explicar"}
CONVENTION = ("Operación = (local nuevo − local previo) × tasa previa; tipo de cambio = local nuevo × (tasa nueva − "
              "tasa previa). Es una convención del equipo: SUPUESTO metodológico.")
TOL = Decimal("0.005")


# ------------------------------------------------------------------ parametros
@dataclass
class VarianceParams:
    min_pct: Decimal = Decimal("0.05")          # SUPUESTO
    min_abs_usd: Decimal = Decimal("10000")     # SUPUESTO


def load_params(path=None) -> VarianceParams:
    p = Path(path) if path else DEFAULT_CONFIG
    if not p.exists():
        return VarianceParams()
    d = json.loads(p.read_text(encoding="utf-8"))
    return VarianceParams(Decimal(str(d.get("min_pct", "0.05"))), Decimal(str(d.get("min_abs_usd", "10000"))))


def validate_params(params: VarianceParams) -> List[Finding]:
    """Un umbral mal escrito no pasa inadvertido: bloquea el explicador."""
    out: List[Finding] = []

    def add(rule, sev, msg, found, expected, sug):
        out.append(Finding(f"F-{rule}-{len(out) + 1:02d}", rule, sev, msg, [], None, None, str(found), str(expected),
                           sug))
    if not (0 <= params.min_pct < 1):
        add("VAR-01", BLOCK, f"Umbral porcentual fuera de rango ({params.min_pct}): debe ser una fraccion entre 0 y 1 "
            f"(5% = 0.05)", params.min_pct, "0 <= p < 1", "Corregir config/variance.json")
    elif params.min_pct > Decimal("0.5"):
        add("VAR-01", WARN, f"Umbral porcentual muy alto ({params.min_pct:.0%}): casi nada seria material",
            params.min_pct, "<= 50%", "Confirmar el supuesto")
    if params.min_abs_usd < 0:
        add("VAR-02", BLOCK, f"Umbral absoluto negativo ({params.min_abs_usd})", params.min_abs_usd, ">= 0",
            "Corregir config/variance.json")
    elif params.min_abs_usd == 0 and params.min_pct == 0:
        add("VAR-02", WARN, "Ambos umbrales en 0: toda variacion es material", 0, "> 0", "Confirmar el supuesto")
    return out


# ------------------------------------------------------------------ estructuras
@dataclass
class ConsolidatedView:
    """Un periodo del consolidado del motor (RunResult + periodo)."""
    run: object
    period: str


def view(run, period: str) -> ConsolidatedView:
    return ConsolidatedView(run, period)


@dataclass
class TraceRow:
    period: str
    company_id: str
    file: str
    sheet: Optional[str]
    row: int
    account_local: Optional[str]
    local: Optional[Decimal]
    currency: Optional[str]
    rate: Optional[Decimal]
    usd: Optional[Decimal]
    status: str
    rule: str


@dataclass
class Variation:
    key: str
    label: str
    prev_period: str
    cur_period: str
    prev: Decimal
    cur: Decimal
    total: Decimal
    pct: Optional[Decimal]
    causes: Dict[str, Decimal]
    material: bool = False
    tags: List[str] = field(default_factory=list)       # PROVISIONAL / SUPUESTO
    notes: List[str] = field(default_factory=list)
    phrase: str = ""
    trace: List[TraceRow] = field(default_factory=list)

    @property
    def causes_sum(self) -> Decimal:
        return sum(self.causes.values(), D0)


@dataclass
class VarianceReport:
    prev_period: str
    cur_period: str
    params: VarianceParams
    findings: List[Finding]
    by_account: Dict[str, Variation] = field(default_factory=dict)
    by_company: Dict[str, Variation] = field(default_factory=dict)
    cells: Dict[Tuple[str, str], Variation] = field(default_factory=dict)
    total: Optional[Variation] = None
    outside: List[str] = field(default_factory=list)    # registros fuera del consolidado (informativo)
    provisional: bool = False
    convention: str = CONVENTION

    @property
    def blocked(self) -> bool:
        return any(f.severity == BLOCK for f in self.findings)


# ------------------------------------------------------------------ formulas puras
def decompose(local_prev: Decimal, local_new: Decimal, rate_prev: Decimal, rate_new: Decimal) -> Tuple[Decimal, Decimal]:
    """(operacion, tipo de cambio). Ej.: 1,000,000 x 0.05 -> 1,100,000 x 0.0525 = +7,750 = +5,000 + 2,750."""
    return (local_new - local_prev) * rate_prev, local_new * (rate_new - rate_prev)


def fmt(d: Decimal) -> str:
    return f"{d:,.2f}"


def sfmt(d: Decimal) -> str:
    return f"{d:+,.2f}"


# ------------------------------------------------------------------ celdas (empresa x cuenta)
@dataclass
class _Cell:
    records: list = field(default_factory=list)
    gross: Decimal = D0            # todo lo valorable cargado (OK + duplicado excluido + bloqueado)
    local: Dict[str, Decimal] = field(default_factory=lambda: defaultdict(Decimal))
    excl: Decimal = D0             # bloqueados valorables (no entran al consolidado)
    dup: Decimal = D0              # ajuste de duplicados excluidos (negativo)
    ok: Decimal = D0
    elim: Decimal = D0
    unvalued: list = field(default_factory=list)

    @property
    def cons(self) -> Decimal:
        return self.ok + self.elim


def _cells(run, period) -> Tuple[Dict[Tuple[str, str], _Cell], set]:
    adj = {rid: a for a in run.adjustments if a.kind == "IC_ELIMINATION" for rid in a.record_ids}
    cells: Dict[Tuple[str, str], _Cell] = defaultdict(_Cell)
    present = {r.company_id for r in run.records if r.period == period}
    for r in run.records:
        if r.period != period or not r.account_code or r.status == TOTAL:
            continue
        c = cells[(r.company_id, r.account_code)]
        c.records.append(r)
        usd = r.amount_usd
        if r.status in (OK, EXCLUDED_DUPLICATE, BLOCKED) and usd is not None:
            c.gross += usd
            c.local[r.currency] += r.amount_original
            if r.status == BLOCKED:
                c.excl += usd
            elif r.status == EXCLUDED_DUPLICATE:
                c.dup -= usd
        elif r.status == BLOCKED:
            c.unvalued.append(r)
        if r.status == OK and usd is not None:
            c.ok += usd
        a = adj.get(r.record_id)
        if a:
            c.elim += a.amount_usd
    return cells, present


def _rate(cfg, period, cur) -> Optional[Decimal]:
    fx = cfg.rates.get((period, cur))
    if fx is None:
        return Decimal(1) if cur == cfg.base_currency else None
    return to_usd(Decimal(1), fx) if fx.rate > 0 else None


def _cell_variation(cfg, cid, code, p0, p1, c0: _Cell, c1: _Cell, present0, present1) -> Variation:
    causes = {k: D0 for k in CAUSES}
    notes: List[str] = []
    if cid not in present0 or cid not in present1:
        faltante = p0 if cid not in present0 else p1
        causes[MES] = c1.gross - c0.gross
        notes.append(f"La empresa {cid} no entrego datos de {faltante}: el movimiento se debe a esa ausencia.")
    else:
        normal = True
        if c0.unvalued or c1.unvalued:
            normal = False
            for r in c0.unvalued + c1.unvalued:
                notes.append(f"Registro bloqueado sin valor en USD ({r.currency!r}, {r.amount_original}): "
                             f"{'; '.join(r.status_reasons)}. No se puede atribuir el movimiento de esta cuenta.")
        if c0.local and c1.local and set(c0.local) != set(c1.local):
            normal = False
            notes.append(f"La moneda del registro cambio entre periodos ({', '.join(sorted(c0.local))} -> "
                         f"{', '.join(sorted(c1.local))}): no se puede separar operacion de tipo de cambio.")
        rates = {}
        for cur in set(c0.local) | set(c1.local):
            rp, rn = _rate(cfg, p0, cur), _rate(cfg, p1, cur)
            if rp is None or rn is None:
                normal = False
                notes.append(f"Falta la tasa de {cur} en {p0 if rp is None else p1}.")
            rates[cur] = (rp, rn)
        if normal:
            for cur, (rp, rn) in rates.items():
                op, fx = decompose(c0.local.get(cur, D0), c1.local.get(cur, D0), rp, rn)
                causes[OP] += op
                causes[FX] += fx
    causes[ELIM] = c1.elim - c0.elim
    causes[AJ] = -(c1.excl - c0.excl) + (c1.dup - c0.dup)
    total = c1.cons - c0.cons
    causes[SIN] = total - sum((v for k, v in causes.items() if k != SIN), D0)
    if abs(causes[SIN]) < TOL:
        causes[SIN] = D0
    prev, cur = c0.cons, c1.cons
    return Variation(f"{cid}|{code}", f"{cid} {cfg.catalog[code].name} ({code})", p0, p1, prev, cur, total,
                     (total / abs(prev)) if prev else None, causes, notes=notes)


# ------------------------------------------------------------------ agregacion
def _sum(vs: List[Tuple[Variation, int]], key, label, p0, p1) -> Variation:
    prev = sum((s * v.prev for v, s in vs), D0)
    cur = sum((s * v.cur for v, s in vs), D0)
    total = cur - prev
    causes = {k: sum((s * v.causes[k] for v, s in vs), D0) for k in CAUSES}
    causes[SIN] = total - sum((x for k, x in causes.items() if k != SIN), D0)
    if abs(causes[SIN]) < TOL:
        causes[SIN] = D0
    notes = []
    for v, _ in vs:
        for n in v.notes:
            if n not in notes:
                notes.append(n)
    return Variation(key, label, p0, p1, prev, cur, total, (total / abs(prev)) if prev else None, causes, notes=notes)


def _material(v: Variation, params: VarianceParams) -> bool:
    return abs(v.total) >= params.min_abs_usd and (v.pct is None or abs(v.pct) >= params.min_pct)


def _phrase(v: Variation) -> str:
    if v.total == 0:
        return f"{v.label} no cambia entre {v.prev_period} y {v.cur_period}: {fmt(v.cur)} USD."
    verbo = "sube" if v.total > 0 else "baja"
    pct = f" ({v.pct:+.1%})" if v.pct is not None else " (nueva)"
    s = (f"{v.label} {verbo} {fmt(abs(v.total))} USD{pct} entre {v.prev_period} y {v.cur_period}, de {fmt(v.prev)} "
         f"a {fmt(v.cur)} USD.")
    partes = [f"{CAUSE_NAMES[k].lower()} {sfmt(x)} USD" for k, x in v.causes.items() if x != 0]
    if partes:
        s += " Por causa: " + "; ".join(partes) + "."
    if v.causes[SIN] != 0:
        s += " Hay una parte sin explicar: los datos no prueban la causa (ver notas)."
    if "PROVISIONAL" in v.tags:
        s += " [PROVISIONAL]"
    return s


def _trace(run, cells_keys, p0, p1, adj_rule) -> List[TraceRow]:
    cfg = run.config
    out = []
    for r in run.records:
        if r.period not in (p0, p1) or r.status == TOTAL or (r.company_id, r.account_code) not in cells_keys:
            continue
        rules = [adj_rule[a] for a in r.adjustment_ids if a in adj_rule]
        rule = "; ".join(rules) if rules else ("; ".join(r.status_reasons) if r.status_reasons else "OK")
        out.append(TraceRow(r.period, r.company_id, r.source_file, r.source_sheet, r.source_row, r.account_local,
                            r.amount_original, r.currency, r.fx_rate, r.amount_usd, r.status, rule))
    return sorted(out, key=lambda t: (t.period, t.company_id, t.row))


# ------------------------------------------------------------------ comparacion
def compare(prev: ConsolidatedView, cur: ConsolidatedView, records=None, params: Optional[VarianceParams] = None
            ) -> VarianceReport:
    """Compara dos periodos del mismo consolidado. `records` se ignora (se toma del RunResult)."""
    run = cur.run
    cfg = run.config
    params = params or load_params()
    p0, p1 = prev.period, cur.period
    rep = VarianceReport(p0, p1, params, validate_params(params))
    if rep.blocked:
        return rep
    pr0, pr1 = prev.run.periods[p0], run.periods[p1]
    rep.provisional = pr0.provisional or pr1.provisional
    tags = (["PROVISIONAL"] if rep.provisional else [])

    cells0, present0 = _cells(prev.run, p0)
    cells1, present1 = _cells(run, p1)
    keys = sorted(set(cells0) | set(cells1))
    for (cid, code) in keys:
        rep.cells[(cid, code)] = _cell_variation(cfg, cid, code, p0, p1, cells0.get((cid, code), _Cell()),
                                                 cells1.get((cid, code), _Cell()), present0, present1)

    adj_rule = {a.adjustment_id: f"{a.rule} ({a.reason})" for a in run.adjustments}
    by_acc = defaultdict(list)
    by_co = defaultdict(list)
    all_util = []
    for (cid, code), v in rep.cells.items():
        by_acc[code].append((v, 1))
        sign = UTILITY_SIGN.get(cfg.catalog[code].cls, 0)
        if sign:
            by_co[cid].append((v, sign))
            all_util.append((v, sign))
    for code, vs in by_acc.items():
        a = _sum(vs, code, f"{cfg.catalog[code].name} ({code})", p0, p1)
        a.trace = _trace(run, {(cid, code) for cid in {x[0].key.split("|")[0] for x in vs}}, p0, p1, adj_rule)
        rep.by_account[code] = a
    for cid, vs in by_co.items():
        v = _sum(vs, cid, f"{cfg.companies[cid].name} ({cid}), efecto en la utilidad neta", p0, p1)
        v.trace = _trace(run, {(cid, x[0].key.split("|")[1]) for x in vs}, p0, p1, adj_rule)
        rep.by_company[cid] = v
    rep.total = _sum(all_util, "TOTAL", "La utilidad neta consolidada", p0, p1)
    rep.total.trace = _trace(run, {(x[0].key.split("|")[0], x[0].key.split("|")[1]) for x in all_util}, p0, p1, adj_rule)

    for v in list(rep.by_account.values()) + list(rep.by_company.values()) + [rep.total]:
        v.material = _material(v, params)
        v.tags = list(tags) + (["SUPUESTO"] if (v.causes[OP] != 0 or v.causes[FX] != 0) else [])
        v.phrase = _phrase(v)
    for v in rep.cells.values():
        v.material = _material(v, params)
        v.tags = list(tags)

    for p, view_ in ((p0, prev), (p1, cur)):
        for e in view_.run.periods[p].excluded:
            monto = (f"{fmt(e.amount_usd)} USD" if e.amount_usd is not None else "sin valor en USD")
            rep.outside.append(f"{p}: {e.record_id} [{e.status}] {monto}: {'; '.join(e.reasons)}")
    return rep


def pairs(run) -> List[Tuple[str, str]]:
    """Pares consecutivos de periodos del consolidado: (previo, actual)."""
    ps = sorted(run.periods)
    return list(zip(ps, ps[1:]))
