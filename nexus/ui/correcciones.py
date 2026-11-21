"""Propuestas de correccion, aprobacion humana y recalculo (sin tocar el motor ni los archivos fuente).

Cada hallazgo termina en UNA de dos acciones:
  APLICADA_AUTOMATICAMENTE  solo el duplicado exacto con el mismo ID: el motor ya lo excluyo con un ajuste
                            registrado y reversible.
  PROPUESTA                 todo lo demas: el registro queda bloqueado o pendiente y NEXUS propone una correccion
                            (valor, motivo, impacto). Una persona la aprueba o la rechaza.

Aprobar NO modifica ningun archivo: la decision queda en un registro de auditoria (JSONL, solo se agrega) y el
consolidado se recalcula en MEMORIA con run_corregido, que lee los originales en solo lectura y aplica las
correcciones aprobadas. Deshacer registra otro evento y vuelve a recalcular sin esa correccion."""
import datetime as dt
import json
import os
import re
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from statistics import median
from typing import Dict, List, Optional

from .. import audit, consolidation, currency, historial, ingestion, intercompany, validation
from ..adapters import adapter_for
from ..config import load_group_config
from ..consolidation import UTILITY_SIGN
from ..diagnostico import _Ctx, diagnosticar_balance
from ..mapping import map_headers
from ..profiles import apply_profiles, load_profiles
from ..schemas import (BLOCK, BLOCKED, EXCLUDED_DUPLICATE, OK, USD_PER_LOCAL, WARN, Adjustment, Finding, FxRate,
                       Record)
from ..text import norm, parse_amount

ROOT = Path(__file__).resolve().parent.parent.parent
def log_por_defecto() -> Path:
    """Registro de auditoria de aprobaciones (JSONL, solo se agrega). NEXUS_APROBACIONES lo cambia (pruebas)."""
    return Path(os.environ.get("NEXUS_APROBACIONES") or ROOT / "data" / "output" / "aprobaciones.jsonl")


LOG_POR_DEFECTO = log_por_defecto()
AUTO, PROPUESTA = "APLICADA_AUTOMATICAMENTE", "PROPUESTA"
IMPORTE, SIGNO, TASA, MONEDA_ARCHIVO, ASIENTO, DUPLICADO = "IMPORTE", "SIGNO", "TASA", "MONEDA_ARCHIVO", "ASIENTO", \
    "DUPLICADO_EXCLUIDO"
D0 = Decimal(0)


def fmt(d) -> str:
    return "n/c" if d is None else f"{d:,.2f}"


@dataclass
class Propuesta:
    key: str
    kind: str
    accion: str
    rule_id: str
    company_id: Optional[str]
    period: Optional[str]
    record_ids: List[str]
    valor_leido: str
    valor_propuesto: Optional[object]
    motivo: str
    impacto_usd: Optional[Decimal]
    impacto_utilidad: str
    que_hizo: str
    decide: str
    aprobable: bool
    cuenta_requerida: bool = False
    extra: dict = field(default_factory=dict)


# ------------------------------------------------------------------ propuestas
def _raw_monto(res, r) -> str:
    cfg = res.config
    prof = cfg.profiles.get(r.company_id)
    if prof is not None and "amount" in prof.columns:
        v = r.raw.get(prof.columns["amount"])
    else:
        mapping, _ = map_headers(list(r.raw))
        col = next((c for c, f in mapping.items() if f == "amount"), None)
        v = r.raw.get(col) if col else None
    return "(vacío)" if v is None or str(v).strip() == "" else str(v)


def _usd(res, r, valor):
    fx = res.config.rates.get((r.period, r.currency))
    return None if fx is None or fx.rate <= 0 else currency.to_usd(valor, fx)


def _efecto(res, r, usd) -> str:
    a = res.config.catalog.get(r.account_code or "")
    s = UTILITY_SIGN.get(a.cls, 0) if a else 0
    if usd is None:
        return "No se puede calcular sin la tasa."
    if not s:
        return "Es una cuenta de balance: no cambia la utilidad."
    return f"Si se aprueba, la utilidad cambia {s * usd:+,.2f} USD (hoy el registro no entra al consolidado)."


def interpretar_texto(s: str) -> Optional[Decimal]:
    """«1O,000» (letra O) -> 10,000. Solo cambia la letra O por el cero; si aun no es un numero, no propone."""
    cand = str(s).strip().replace("O", "0").replace("o", "0")
    for dec in (".", ","):
        v = parse_amount(cand, dec)
        if v is not None:
            return v
    return None


def _prop_importe(res, f, r) -> Propuesta:
    leido = _raw_monto(res, r)
    key = f"IMPORTE|{r.record_id}"
    base = dict(key=key, kind=IMPORTE, accion=PROPUESTA, rule_id=f.rule_id, company_id=r.company_id, period=r.period,
                record_ids=[r.record_id], valor_leido=leido,
                que_hizo="Dejó el registro bloqueado: no entra al consolidado hasta que una persona decida.")
    prop, motivo = None, ""
    if leido != "(vacío)":
        prop = interpretar_texto(leido)
        motivo = "Se cambió la letra O por el cero en el texto leído." if prop is not None else ""
    elif r.account_code and r.currency:
        otros = {}
        for x in res.records:
            if x.company_id == r.company_id and x.account_code == r.account_code and x.period != r.period \
                    and x.status == OK and x.amount_original is not None and x.currency == r.currency:
                otros[x.period] = otros.get(x.period, D0) + x.amount_original
        if otros:
            prop = Decimal(str(median(otros.values()))).quantize(Decimal("0.01"))
            motivo = (f"Mediana del mismo rubro en los otros períodos ({', '.join(sorted(otros))}). Es una referencia, "
                      f"no una certeza.")
    if prop is None:
        return Propuesta(**base, valor_propuesto=None, motivo="No hay un valor que se pueda proponer con certeza.",
                         impacto_usd=None, impacto_utilidad="No cuantificable sin un valor.",
                         decide="Corregir el dato en el archivo de origen.", aprobable=False)
    usd = _usd(res, r, prop)
    return Propuesta(**base, valor_propuesto=prop, motivo=motivo, impacto_usd=usd,
                     impacto_utilidad=_efecto(res, r, usd),
                     decide=f"Aprobar o rechazar el valor propuesto ({fmt(prop)} {r.currency}).", aprobable=True)


def _prop_signo(res, f, r) -> Propuesta:
    prop = abs(r.amount_original)
    usd = _usd(res, r, prop)
    return Propuesta(f"SIGNO|{r.record_id}", SIGNO, PROPUESTA, f.rule_id, r.company_id, r.period, [r.record_id],
                     str(r.amount_original), prop, "Mismo importe con el signo que corresponde a su cuenta.", usd,
                     _efecto(res, r, usd),
                     "Dejó el registro bloqueado: no entra al consolidado hasta que una persona decida.",
                     f"Aprobar o rechazar el signo corregido (+{fmt(prop)} {r.currency}).", True)


def _prop_tasa(res, f) -> Optional[Propuesta]:
    m = re.search(r"Tasa sospechosa: ([A-Z]{3}) pasa de ([\d.]+) a ([\d.]+) .* entre ([\d-]+) y ([\d-]+)", f.message)
    if not m:
        return None
    cur, prev, new, p0, p1 = m.group(1), Decimal(m.group(2)), Decimal(m.group(3)), m.group(4), m.group(5)
    cands = [new / 10, new / 100, new * 10]
    best = min(cands, key=lambda c: abs(c / prev - 1))
    if abs(best / prev - 1) <= validation.load_rate_jump():
        prop, motivo = best, (f"Parece un decimal corrido: {new} ÷ {new / best:g} = {best}, que queda a "
                              f"{abs(best / prev - 1):.1%} de la tasa del mes anterior ({prev}).")
    else:
        prop, motivo = prev, f"No hay un decimal corrido que lo explique; se propone la tasa del mes anterior ({prev})."
    n = re.findall(r"[-+]?\d[\d,]*\.\d{2}", f.impact or "")
    imp = abs(Decimal(n[0].replace(",", ""))) if n else None
    return Propuesta(f"TASA|{cur}|{p1}", TASA, PROPUESTA, f.rule_id, None, p1, [], new_str(new), prop, motivo, imp,
                     "Diferencia en el consolidado: " + (f.impact or "no cuantificada"),
                     "Usó la tasa tal cual está en la tabla; no la bloqueó ni la corrigió.",
                     f"Confirmar con la fuente oficial. Aprobar o rechazar la tasa propuesta ({prop}).", True,
                     extra={"moneda": cur, "periodo": p1})


def new_str(d) -> str:
    return format(d, "f")


def _prop_moneda_archivo(res, f) -> Optional[Propuesta]:
    m = re.search(r"El archivo declara ([A-Z]{3}) pero el perfil de la empresa dice ([A-Z]{3})", f.message)
    if not m:
        return Propuesta(f"CARGA|{f.company_id}", "CARGA", PROPUESTA, f.rule_id, f.company_id, None, [], "-", None,
                         "La fuente no coincide con su perfil.", None, "La empresa no aporta registros.",
                         "No procesó el archivo: quedó en revisión.",
                         "Corregir el archivo o actualizar y aprobar el perfil.", False)
    declara, perfil = m.group(1), m.group(2)
    return Propuesta(f"MONEDA_ARCHIVO|{f.company_id}", MONEDA_ARCHIVO, PROPUESTA, f.rule_id, f.company_id, None, [],
                     declara, perfil, f"Tratar todas las filas del archivo como {perfil}, la moneda del perfil.", None,
                     "La empresa vuelve a aportar sus registros: cambian ingresos, costos y las eliminaciones con "
                     "las empresas con las que opera.",
                     "No procesó el archivo: quedó en revisión y la empresa no aporta registros.",
                     f"Confirmar con la empresa si sus importes están en {perfil}. Aprobar o rechazar.", True,
                     extra={"declara": declara})


def _prop_asiento(res, f) -> Optional[Propuesta]:
    ctx = _Ctx(res)
    D_, cands, _c = diagnosticar_balance(ctx, f.company_id, f.period)
    if D_ == 0:
        return None
    cls = ("activo",) if D_ < 0 else ("pasivo", "patrimonio")
    opciones = [(c, a.name) for c, a in res.config.catalog.items() if a.cls in cls]
    return Propuesta(f"ASIENTO|{f.company_id}|{f.period}", ASIENTO, PROPUESTA, f.rule_id, f.company_id, f.period, [],
                     f"D = {fmt(D_)} USD", abs(D_),
                     f"Agregar el asiento omitido por {fmt(abs(D_))} USD para que el balance cuadre; NEXUS no sabe en qué "
                     f"cuenta va: la elige una persona.", abs(D_),
                     "No cambia el estado de resultados; hace cuadrar el balance de la empresa en ese período.",
                     "No cambió nada: el registro huérfano sigue en el consolidado y el período queda PROVISIONAL.",
                     "Elegir la cuenta del asiento omitido y aprobar, o rechazar y corregir el archivo de origen.", True,
                     cuenta_requerida=True, extra={"opciones": opciones, "diferencia": D_})


def proponer(res) -> List[Propuesta]:
    recs = {r.record_id: r for r in res.records}
    out: List[Propuesta] = []
    adj_by_rec = {rid: a for a in res.adjustments if a.kind == "DUPLICATE_EXCLUSION" for rid in a.record_ids}
    for f in res.findings:
        r = recs.get(f.record_ids[0]) if f.record_ids else None
        if f.rule_id == "DUP-01":
            for rid in f.record_ids:
                x = recs[rid]
                if x.status == EXCLUDED_DUPLICATE and rid in adj_by_rec:
                    a = adj_by_rec[rid]
                    out.append(Propuesta(f"DUP|{rid}", DUPLICADO, AUTO, "DUP-01", x.company_id, x.period, [rid],
                                         _raw_monto(res, x), None, a.reason, abs(x.amount_usd or D0),
                                         "Contado dos veces inflaría el consolidado; ya está excluido.",
                                         f"Excluyó la fila repetida con el ajuste {a.adjustment_id} (reversible); el "
                                         f"original no se borra.",
                                         "Nada, salvo que el duplicado sea legítimo: entonces puedes revertir la "
                                         "exclusión.", False, extra={"adjustment_id": a.adjustment_id}))
        elif f.rule_id == "ING-01" and r is not None and "Importe no numerico" in " ".join(r.status_reasons):
            out.append(_prop_importe(res, f, r))
        elif f.rule_id == "SIGN-01" and r is not None:
            out.append(_prop_signo(res, f, r))
        elif f.rule_id == "TAS-01":
            p = _prop_tasa(res, f)
            if p:
                out.append(p)
        elif f.rule_id == "CARGA-01":
            out.append(_prop_moneda_archivo(res, f))
        elif f.rule_id == "BAL-01":
            p = _prop_asiento(res, f)
            if p:
                out.append(p)
    return out


# ------------------------------------------------------------------ registro de auditoria
def registrar(log_path, evento: dict) -> dict:
    p = Path(log_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    ev = {"ts": dt.datetime.now().isoformat(timespec="seconds"), **evento}
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(ev, ensure_ascii=False, default=str) + "\n")
    return ev


def leer(log_path) -> List[dict]:
    p = Path(log_path)
    if not p.is_file():
        return []
    return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]


def estado(log_path, escenario: str) -> Dict[str, dict]:
    """key -> ultimo evento vigente (APROBAR o RECHAZAR). DESHACER devuelve la decision a 'pendiente'."""
    cur: Dict[str, dict] = {}
    for ev in leer(log_path):
        if ev.get("escenario") != escenario:
            continue
        if ev["evento"] in ("APROBAR", "RECHAZAR"):
            cur[ev["key"]] = ev
        elif ev["evento"] == "DESHACER":
            cur.pop(ev["key"], None)
    return cur


def aprobaciones(log_path, escenario: str) -> List[dict]:
    return [e for e in estado(log_path, escenario).values() if e["evento"] == "APROBAR"]


def evento_desde(p: Propuesta, evento: str, quien: str, escenario: str, cuenta: Optional[str] = None) -> dict:
    return {"evento": evento, "quien": quien, "escenario": escenario, "key": p.key, "kind": p.kind,
            "rule_id": p.rule_id, "company_id": p.company_id, "period": p.period, "record_ids": p.record_ids,
            "valor_leido": p.valor_leido,
            "valor_propuesto": None if p.valor_propuesto is None else str(p.valor_propuesto),
            "motivo": p.motivo, "impacto_usd": None if p.impacto_usd is None else str(p.impacto_usd),
            "cuenta": cuenta, "extra": {k: v for k, v in p.extra.items() if k in ("moneda", "periodo", "adjustment_id",
                                                                                   "declara")}}


# ------------------------------------------------------------------ recalculo en memoria
def run_corregido(input_dir, profiles_dir=None, aprobadas=(), ic_tolerance_usd="1.00"):
    """Igual que nexus.pipeline.run, pero aplicando en MEMORIA las correcciones aprobadas (lista de eventos APROBAR).
    Los archivos se leen en solo lectura y nunca se modifican. Sin aprobaciones el resultado es identico al del motor."""
    input_dir = Path(input_dir)
    cfg = load_group_config(input_dir, ic_tolerance_usd)
    profiles = None
    if profiles_dir is not None:
        profiles = load_profiles(profiles_dir)
        apply_profiles(cfg, profiles)
    ap = list(aprobadas)
    for a in ap:
        if a["kind"] == TASA:
            cfg.rates[(a["extra"]["periodo"], a["extra"]["moneda"])] = FxRate(
                a["extra"]["periodo"], a["extra"]["moneda"], Decimal(a["valor_propuesto"]), USD_PER_LOCAL)
    files = [input_dir / c.file for c in cfg.companies.values()] + sorted(input_dir.glob("*.csv"))
    if profiles_dir is not None:
        files += sorted(Path(profiles_dir).glob("*.json"))
    hashes = audit.file_hashes([f for f in dict.fromkeys(files) if f.exists()])
    records, load_reports = ingestion.ingest_group_with_reports(input_dir, cfg, profiles)

    for a in [a for a in ap if a["kind"] == MONEDA_ARCHIVO]:
        cid = a["company_id"]
        p = profiles[cid]
        path = input_dir / p.source.file
        ad = adapter_for(p.source.type)
        recs = ad.normalize(ad.extract(path, p), path, cid, cfg, p)
        for r in recs:
            r.currency, r.currency_source = a["valor_propuesto"], "APROBADA"
        records.extend(recs)
        rep = load_reports[cid]
        rep.status, rep.n_records, rep.reasons = "MATCHED", len(recs), []
        rep.notes = [f"Moneda {a['valor_propuesto']} aprobada por {a['quien']} el {a['ts']}"]

    by_id = {r.record_id: r for r in records}
    extra_adj: List[Adjustment] = []
    n_asientos = 0
    for a in ap:
        nota = f"aprobado por {a['quien']} el {a['ts']}: {a['motivo']}"
        if a["kind"] in (IMPORTE, SIGNO):
            r = by_id[a["record_ids"][0]]
            r.amount_original = Decimal(a["valor_propuesto"])
            if r.status == BLOCKED:
                r.status = OK
                r.status_reasons = [x for x in r.status_reasons if "Importe no numerico" not in x]
            r.status_reasons.append("Corregido, " + nota)
        elif a["kind"] == ASIENTO:
            n_asientos += 1
            cat = cfg.catalog[a["cuenta"]]
            r = Record(f"{a['company_id']}|ASIENTO-APROBADO|{n_asientos}", a["company_id"],
                       "(asiento agregado por aprobación)", None, 0, {}, period=a["period"], account_local=cat.name,
                       account_code=a["cuenta"], mapping_status="CONFIRMED", amount_original=Decimal(a["valor_propuesto"]),
                       currency="USD", currency_source="APROBADA", status=OK,
                       status_reasons=["Asiento agregado, " + nota])
            records.append(r)
            by_id[r.record_id] = r
    currency.convert(records, cfg)
    adjustments, findings = validation.apply_record_rules(records, cfg)

    for a in [a for a in ap if a["kind"] == DUPLICADO]:
        adj = next((x for x in adjustments if x.adjustment_id == a["extra"]["adjustment_id"]), None)
        if adj:
            validation.reverse_adjustment(adj, records)
            adjustments.remove(adj)
    for a in ap:
        recs_ids = a["record_ids"]
        usd = None
        for rid in recs_ids:
            r = by_id.get(rid)
            if r is not None:
                r.adjustment_ids.append(f"APROB-{a['key']}")
                usd = r.amount_usd
        extra_adj.append(Adjustment(f"APROB-{a['key']}", "HUMAN_CORRECTION", recs_ids,
                                    usd if usd is not None else D0, a.get("cuenta"), a.get("period"),
                                    f"Valor leído {a['valor_leido']} -> valor aprobado {a['valor_propuesto']}. {a['motivo']}",
                                    "APROB-HUMANA: una persona aprobó la correccion propuesta", True, a["quien"]))
    matches = intercompany.match(records, cfg)
    adjustments += intercompany.eliminations(matches, records)
    adjustments += extra_adj
    for m in matches:
        if m.status != "RECONCILED":
            findings.append(Finding(f"F-IC-{m.match_id}", "IC-01", WARN if m.status == "DISCREPANCY" else BLOCK,
                                    f"{m.seller_id} registra {m.seller_usd:,.2f} USD y {m.buyer_id} registra "
                                    f"{m.buyer_usd:,.2f} USD (ref {m.reference or 's/ref'}): diferencia "
                                    f"{m.difference_usd:,.2f} USD. No se elimina.",
                                    m.seller_record_ids + m.buyer_record_ids, m.period, m.seller_id,
                                    f"{m.seller_usd} vs {m.buyer_usd}", "montos iguales",
                                    "Conciliar con ambas empresas antes de eliminar"))
    for rep in load_reports.values():
        if rep.status == "REVIEW":
            findings.append(Finding(f"F-CARGA-{rep.company_id}", "CARGA-01", BLOCK,
                                    f"La carga de {rep.company_id} ({rep.file}) quedo en REVISION y no aporta "
                                    f"registros: " + "; ".join(rep.reasons), [], None, rep.company_id,
                                    suggestion="Corregir el archivo o actualizar y aprobar el perfil"))
    by_hash = {}
    for c in cfg.companies.values():
        h = hashes.get(c.file)
        if h:
            by_hash.setdefault(h, []).append(c)
    for h, cs in by_hash.items():
        if len(cs) > 1:
            findings.append(Finding(f"F-ARC-{cs[0].company_id}", "ARC-01", WARN,
                                    "Los archivos " + " y ".join(c.file for c in cs) + " son identicos (mismo "
                                    f"SHA-256 {h[:16]}...): posible reenvio del mismo archivo bajo otro nombre.",
                                    [], None, cs[0].company_id, h[:16], "archivos distintos",
                                    "Confirmar cual es el archivo correcto de cada empresa"))
    findings += validation.validate(records, cfg)
    periods = consolidation.consolidate(records, adjustments, matches, findings, cfg)
    run_id = dt.datetime.now().strftime("run-%Y%m%d-%H%M%S")
    from ..schemas import RunResult
    res = RunResult(run_id, cfg, records, adjustments, matches, findings, periods, hashes, load_reports)
    res.aprobaciones_aplicadas = ap
    return res
