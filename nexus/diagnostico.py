"""Diagnostico y fichas de hallazgos (plantillas en espanol, sin IA).

Por cada hallazgo bloqueado o marcado genera una ficha: que paso, donde (archivo, hoja, fila), por que importa
(impacto en USD y en utilidad), causa PROBABLE y accion humana recomendada. Reglas de redaccion:
  - la causa siempre dice "probable": son hipotesis, nunca certezas;
  - nunca se atribuye el error a personas; se habla de datos, archivos y procesos;
  - FinaCore no corrige ni convierte nada solo: la accion siempre la toma una persona.
Todo es calculo determinista con Decimal sobre el resultado del motor."""
import re
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from .consolidation import UTILITY_SIGN
from .currency import to_usd
from .schemas import BLOCKED, EXCLUDED_DUPLICATE, FLAG_POSSIBLE_DUPLICATE, OK, PENDING_MAPPING, TOTAL

D0 = Decimal(0)
TOL = Decimal("0.01")

DUPLICADO, MONEDA_SOSPECHOSA, IMPORTE_ATIPICO = "DUPLICADO", "MONEDA_SOSPECHOSA", "IMPORTE_ATIPICO"
TASA_INVALIDA, TASA_SOSPECHOSA = "TASA_INVALIDA", "TASA_SOSPECHOSA"
BALANCE, INTERCOMPANIA = "BALANCE_DESCUADRADO", "DISCREPANCIA_INTERCOMPANIA"
SIN_MAPEAR, FECHA, MONEDA_NO_RECONOCIDA = "CUENTA_SIN_MAPEAR", "FECHA_FUERA_DE_PERIODO", "MONEDA_NO_RECONOCIDA"
MONEDA_FALTANTE, TOTAL_DESC, SIGNO = "MONEDA_FALTANTE", "TOTAL_DESCUADRADO", "SIGNO_INVERTIDO"
MES_FALTANTE, CARGA, NO_NUMERICO, REENVIO, OTRO = "MES_FALTANTE", "CARGA_EN_REVISION", "IMPORTE_NO_NUMERICO", \
    "POSIBLE_REENVIO", "OTRO"

NOMBRES = {
    DUPLICADO: "Duplicado", MONEDA_SOSPECHOSA: "Moneda sospechosa", IMPORTE_ATIPICO: "Importe atípico",
    TASA_INVALIDA: "Tasa de cambio inválida o faltante", TASA_SOSPECHOSA: "Tasa de cambio sospechosa",
    BALANCE: "Balance descuadrado", INTERCOMPANIA: "Discrepancia intercompañía", SIN_MAPEAR: "Cuenta sin mapear",
    FECHA: "Fecha fuera de período", MONEDA_NO_RECONOCIDA: "Moneda no reconocida", MONEDA_FALTANTE: "Moneda faltante",
    TOTAL_DESC: "Total que no cuadra", SIGNO: "Signo invertido", MES_FALTANTE: "Mes faltante",
    CARGA: "Carga en revisión", NO_NUMERICO: "Dato no numérico o fecha inválida", REENVIO: "Posible reenvío",
    OTRO: "Otro hallazgo"}

# Alias de moneda: se SUGIERE un candidato cuando el texto esta contenido en un unico codigo conocido ("Q" en
# GTQ). Es una pista para la persona que decide; nunca se aplica.
ALIAS_CONOCIDOS = {"Q": "GTQ", "QTZ": "GTQ", "MXP": "MXN", "US$": "USD", "U$S": "USD"}


@dataclass
class Ubicacion:
    company_id: str
    file: str
    sheet: Optional[str]
    row: Optional[int]
    period: Optional[str]
    account_local: Optional[str]
    importe: Optional[Decimal]
    moneda: Optional[str]
    usd: Optional[Decimal]
    status: str = ""


@dataclass
class Candidato:
    orden: int
    tipo: str
    descripcion: str
    registros: List[Ubicacion] = field(default_factory=list)


@dataclass
class Ficha:
    ficha_id: str
    tipo: str
    titulo: str
    rule_id: str
    severidad: str
    period: Optional[str]
    company_id: Optional[str]
    que_paso: str
    donde: List[Ubicacion]
    por_que_importa: str
    impacto_usd: Optional[Decimal]
    impacto_estimado: bool
    impacto_utilidad: str
    causa_probable: str
    accion: str
    candidatos: List[Candidato] = field(default_factory=list)
    cercanos: List[Ubicacion] = field(default_factory=list)
    diferencia: Optional[Decimal] = None          # balance: D = activo - (pasivo + patrimonio)
    causa_identificada: Optional[bool] = None     # balance: hay al menos un candidato


def fmt(d) -> str:
    return "n/c" if d is None else f"{d:,.2f}"


_NUM = re.compile(r"[-+]?\d[\d,]*\.\d{2}")


def _nums(s) -> List[Decimal]:
    return [Decimal(x.replace(",", "")) for x in _NUM.findall(s or "")]


# ------------------------------------------------------------------ utilidades
class _Ctx:
    def __init__(self, run):
        self.run = run
        self.cfg = run.config
        self.recs = {r.record_id: r for r in run.records}

    def ub(self, r) -> Ubicacion:
        return Ubicacion(r.company_id, r.source_file, r.source_sheet, r.source_row, r.period, r.account_local,
                         r.amount_original, r.currency, r.amount_usd, r.status)

    def ubs(self, ids) -> List[Ubicacion]:
        return [self.ub(self.recs[i]) for i in ids if i in self.recs]

    def sign(self, r) -> int:
        a = self.cfg.catalog.get(r.account_code or "")
        return UTILITY_SIGN.get(a.cls, 0) if a else 0

    def impact_range(self, r):
        pr = self.run.periods.get(r.period)
        return next((i for i in (pr.impact_ranges if pr else []) if i.record_id == r.record_id), None)


def _alias_probable(codigo: Optional[str], ctx: _Ctx) -> Optional[str]:
    if not codigo:
        return None
    known = {c for (_p, c) in ctx.cfg.rates} | {ctx.cfg.base_currency}
    c = codigo.strip().upper()
    if ALIAS_CONOCIDOS.get(c) in known:
        return ALIAS_CONOCIDOS[c]
    candidatos = [k for k in known if c and c in k and c != k]
    return candidatos[0] if len(candidatos) == 1 else None


def _efecto_texto(r, ctx) -> str:
    s = ctx.sign(r)
    if not s or r.amount_usd is None:
        return "no afecta la utilidad (cuenta de balance) o no se puede valorar en USD"
    return f"{s * r.amount_usd:+,.2f} USD en la utilidad si entrara tal como viene"


# ------------------------------------------------------------------ constructores por tipo
def _dup(f, ctx, recs):
    excl = [r for r in recs if r.status == EXCLUDED_DUPLICATE]
    base = excl or recs[1:] or recs
    usd = sum((r.amount_usd for r in base if r.amount_usd is not None), D0)
    r0 = base[0]
    s = ctx.sign(r0)
    if f.rule_id == "DUP-01":
        imp = (f"De no excluirse, {r0.account_local} se contaría dos veces ({fmt(usd)} USD de más). Ya se excluyó con "
               f"un ajuste registrado y reversible: el consolidado NO está inflado.")
        util = (f"Sin la exclusión la utilidad cambiaría {s * usd:+,.2f} USD." if s else "No afecta la utilidad.")
        causa = "Probable reenvío o doble captura de la misma factura (mismo ID de transacción)."
        acc = ("Confirmar con la empresa que es una sola operación y corregir el archivo de origen. Si resultara "
               "legítima, el ajuste se puede revertir.")
    elif f.rule_id == "DUP-02":
        imp = (f"Si fuera duplicado, {r0.account_local} estaría inflado en {fmt(usd)} USD. Ambos registros siguen en "
               f"el consolidado hasta que una persona decida.")
        util = (f"Si fuera duplicado, la utilidad cambiaría {-s * usd:+,.2f} USD al excluirlo." if s
                else "No afecta la utilidad.")
        causa = ("Probable doble captura (mismo importe, fecha y contraparte, sin ID); también es posible que sean "
                 "dos operaciones distintas e iguales.")
        acc = "Confirmar con la empresa si es una sola operación. FinaCore no excluye sin confirmación humana."
        usd = (r0.amount_usd or D0)
    elif f.rule_id == "DUP-03":
        imp = (f"El mismo ID aparece en archivos de empresas distintas por {fmt(usd)} USD; si es una sola operación "
               f"estaría contada dos veces. Ambos siguen en el consolidado.")
        util = "Depende de la cuenta: si fuera duplicado, la utilidad cambiaría al excluir uno."
        causa = "Probable doble registro de la misma operación en dos archivos."
        acc = "Confirmar con las empresas cuál es el registro válido."
    else:
        imp = "Dos archivos idénticos pueden duplicar todas sus cifras si ambos se consideran válidos."
        util = "No cuantificable: depende de cuál sea el archivo correcto."
        causa = "Probable reenvío del mismo archivo bajo otro nombre."
        acc = "Confirmar cuál es el archivo correcto de cada empresa y retirar el repetido."
    return imp, usd, False, util, causa, acc


def _ficha_generica(f, ctx, recs, tipo):
    usd = sum((abs(r.amount_usd) for r in recs if r.amount_usd is not None), D0)
    return (f.message, usd if recs else None, False, "No cuantificado.", "Causa no determinada; es probable que "
            "requiera revisión de los datos de origen.", "Revisar el hallazgo y corregir el archivo de origen.")


def _moneda_sospechosa(f, ctx, recs):
    nums = _nums(f.found) + _nums(f.expected)
    dif = abs(nums[0] - nums[1]) if len(nums) >= 2 else None
    x = re.search(r"y ([A-Z]{3}) lo\s+explica", f.message or "")
    x = x.group(1) if x else "otra moneda"
    m = re.search(r"(Efecto en utilidad si fuera [A-Z]{3}: [+-][\d,]+\.\d{2} USD\.|La cuenta es de balance: no afecta"
                  r" la utilidad\.)", f.impact or "")
    util = m.group(1) if m else "No cuantificado."
    comp = re.search(r"(Como [A-Z]{3}: [\d,]+\.\d{2} USD \| como [A-Z]{3}: [\d,]+\.\d{2} USD)", f.impact or "")
    imp = (f"{f.message} " + (comp.group(1) + "." if comp else "") +
           " El importe sigue en el consolidado sin modificar y el período queda PROVISIONAL.")
    causa = (f"Probable moneda equivocada: el importe parece estar expresado en {x} y no en la moneda con la que se "
             f"marcó (la razón contra el historial coincide con una tasa de cambio). Es una hipótesis, no una certeza.")
    acc = f"Confirmar la moneda del importe con la empresa y corregir el archivo si corresponde. FinaCore no corrige solo."
    return imp, dif, True, util, causa, acc


def _moneda_no_reconocida(f, ctx, recs):
    r = recs[0] if recs else None
    codigo = r.currency if r else None
    alias = _alias_probable(codigo, ctx)
    est, ir, util = None, (ctx.impact_range(r) if r else None), ""
    if r and alias and r.amount_original is not None and (r.period, alias) in ctx.cfg.rates:
        est = to_usd(r.amount_original, ctx.cfg.rates[(r.period, alias)])
    if ir:
        quien = alias or "la moneda funcional de la empresa"
        util = (f"Mientras tanto el registro queda FUERA del consolidado (utilidad mostrada sin él). Si fuera {quien}, "
                f"la utilidad cambiaría {fmt(ir.utility_corrected)} USD (hipótesis, no asumida).") \
            if ir.utility_corrected is not None else \
            "Queda fuera del consolidado; su efecto en la utilidad no se puede calcular sin conocer la moneda."
    else:
        util = "Queda fuera del consolidado; su efecto en la utilidad no se puede calcular sin conocer la moneda."
    if alias:
        causa = (f"Probable alias de {alias}: «{codigo}» suele ser el símbolo de esa moneda. Es solo una sospecha: "
                 f"requiere aprobación humana en el perfil de la empresa y FinaCore NO convierte el importe por su cuenta.")
        acc = (f"Una persona debe confirmar si «{codigo}» equivale a {alias}: corregir el archivo de origen "
               f"(escribir {alias}) o aprobar el alias en el perfil de la empresa. Hoy los perfiles no admiten alias de "
               f"moneda, por lo que la vía disponible es corregir el archivo.")
        imp = (f"El registro ({fmt(r.amount_original) if r else 'n/c'} «{codigo}») no se puede valorar en USD y no entra "
               f"al consolidado. Si fuera {alias}, valdría aproximadamente {fmt(est)} USD (estimación, no aplicada).")
    else:
        causa = (f"Probable código de moneda mal escrito o de una moneda que el grupo no tiene configurada "
                 f"(«{codigo}»).")
        acc = "Corregir el código de moneda en el archivo de origen, o agregar la moneda y su tasa si es nueva."
        imp = f"El registro no se puede valorar en USD y no entra al consolidado."
    return imp, est, est is not None, util, causa, acc


def _moneda_faltante(f, ctx, recs):
    return ("El registro no declara moneda y no entra al consolidado.", None, False,
            "Queda fuera del consolidado; su efecto en la utilidad no se puede calcular sin la moneda.",
            "Probable celda de moneda vacía en el archivo de origen o una columna no cargada.",
            "Completar la moneda en el archivo de origen y volver a cargar.")


def _tasa_invalida(f, ctx, recs):
    return ("El registro no se puede convertir a USD y no entra al consolidado: " + (recs[0].status_reasons[0]
            if recs and recs[0].status_reasons else f.message), None, False,
            "Queda fuera del consolidado; su efecto en la utilidad no se puede calcular sin la tasa.",
            "Probable tasa ausente, vacía o en cero en la tabla de tasas del mes.",
            "Cargar la tasa correcta del mes en la tabla de tasas y volver a ejecutar.")


def _tasa_sospechosa(f, ctx, recs):
    n = _nums(f.impact)
    return (f.message, abs(n[0]) if n else None, True, "Ver impacto: " + (f.impact or "no cuantificado"),
            "Probable error de captura en la tasa (por ejemplo un decimal corrido) o un cambio real y fuerte de la "
            "moneda. Es una sospecha, no una certeza.",
            "Confirmar la tasa del mes con la fuente oficial. FinaCore no la corrige ni bloquea la carga.")


def _sin_mapear(f, ctx, recs):
    r = recs[0]
    ir = ctx.impact_range(r)
    util = (f"La clase de la cuenta es desconocida: la utilidad podría cambiar entre {fmt(ir.utility_low)} y "
            f"{fmt(ir.utility_high)} USD según a qué cuenta se asigne.") if ir else "No cuantificado."
    return (f"El registro ({fmt(r.amount_original)} {r.currency}, {fmt(r.amount_usd)} USD) no entra al consolidado "
            f"hasta mapear su cuenta.", abs(r.amount_usd) if r.amount_usd is not None else None, False, util,
            "Probable cuenta nueva o escrita con otro nombre que aún no está en las equivalencias del perfil.",
            "Una persona debe mapearla a una cuenta del catálogo común y aprobar el perfil. FinaCore no adivina la cuenta.")


def _fecha(f, ctx, recs):
    r = recs[0] if recs else None
    return (f.message + ". El registro queda fuera del consolidado.", abs(r.amount_usd) if r and r.amount_usd is not None
            else None, False, "Queda fuera del consolidado; la utilidad mostrada no lo incluye.",
            "Probable fecha mal escrita o registro de otro ejercicio.",
            "Corregir la fecha en el archivo de origen o ampliar el calendario del grupo si corresponde.")


def _total(f, ctx, recs):
    nums = _nums(f.found) + _nums(f.expected)
    dif = abs(nums[0] - nums[1]) if len(nums) >= 2 else None
    return (f.message, dif, False,
            "El consolidado usa las partidas, no el total declarado: la utilidad no se ve afectada por este total.",
            "Probable total desactualizado o una partida modificada después de calcular el total.",
            "Corregir el total o la partida que lo desajusta en el archivo de origen.")


def _signo(f, ctx, recs):
    r = recs[0]
    ir = ctx.impact_range(r)
    util = (f"Excluido (como está): {fmt(ir.utility_excluded)} USD; si entrara tal como viene: "
            f"{fmt(ir.utility_as_is)} USD; con el signo corregido: {fmt(ir.utility_corrected)} USD.") if ir else \
        "No afecta la utilidad."
    return (f"El importe ({fmt(r.amount_original)} {r.currency}, {fmt(r.amount_usd)} USD) tiene el signo contrario al "
            f"esperado para su cuenta; queda fuera del consolidado.", abs(r.amount_usd) if r.amount_usd is not None
            else None, False, util,
            "Probable captura con el signo contrario o una convención de signos distinta en el sistema de origen.",
            "Corregir el signo en el archivo de origen y volver a cargar.")


def _mes(f, ctx, recs):
    return (f.message, None, False, "El consolidado del mes no incluye a la empresa: sus cifras quedan subestimadas "
            "y no se puede calcular el efecto en la utilidad.",
            "Probable archivo incompleto o aún no entregado.",
            "Pedir el archivo del mes faltante a la empresa.")


def _carga(f, ctx, recs):
    return (f.message, None, False, "La empresa no aporta registros: sus cifras faltan en el consolidado.",
            "Probable cambio de formato del archivo o un perfil desactualizado.",
            "Corregir el archivo o actualizar y aprobar el perfil de la empresa.")


def _no_numerico(f, ctx, recs):
    return (f.message, None, False, "El registro queda fuera del consolidado; no se puede calcular su efecto.",
            "Probable texto o formato inesperado en la celda (por ejemplo «N/A»).",
            "Corregir el dato en el archivo de origen y volver a cargar.")


def _reenvio(f, ctx, recs):
    return (f.message, None, False, "No cuantificado: depende de si el archivo ya fue consolidado antes.",
            "Probable reenvío del mismo archivo o de la misma operación en otra ejecución.",
            "Confirmar que no se esté consolidando dos veces la misma información.")


# ------------------------------------------------------------------ balance descuadrado
def diagnosticar_balance(ctx: _Ctx, cid: str, period: str) -> Tuple[Decimal, List[Candidato], List[Ubicacion]]:
    """Causas candidatas (deterministas, en orden) de D = activo - (pasivo + patrimonio) de una empresa/periodo."""
    cat = ctx.cfg.catalog
    recs = [r for r in ctx.run.records if r.company_id == cid and r.period == period and r.status != TOTAL]
    sums = defaultdict(lambda: D0)
    for r in recs:
        if r.status == OK and r.amount_usd is not None and r.account_code and cat[r.account_code].cls in (
                "activo", "pasivo", "patrimonio"):
            sums[cat[r.account_code].cls] += r.amount_usd
    D_ = sums["activo"] - sums["pasivo"] - sums["patrimonio"]
    A = abs(D_)
    valued = [r for r in recs if r.amount_usd is not None]
    cands: List[Candidato] = []

    m1 = [r for r in valued if abs(abs(r.amount_usd) - A) <= TOL]
    if m1:
        cands.append(Candidato(1, "REGISTRO_IGUAL_A_D", f"Hay {len(m1)} registro(s) cuyo importe es igual al desbalance "
                               f"({fmt(A)} USD): podría ser un asiento omitido o sobrante.", [ctx.ub(r) for r in m1[:5]]))
    m2 = [r for r in valued if abs(abs(r.amount_usd) * 2 - A) <= TOL]
    if m2:
        cands.append(Candidato(2, "SIGNO_INVERTIDO", f"Hay {len(m2)} registro(s) cuyo importe × 2 es igual al "
                               f"desbalance ({fmt(A)} USD): podría tener el signo invertido.", [ctx.ub(r) for r in m2[:5]]))
    m3 = [r for r in valued if (r.status == EXCLUDED_DUPLICATE or FLAG_POSSIBLE_DUPLICATE in r.flags)
          and abs(abs(r.amount_usd) - A) <= TOL]
    if m3:
        cands.append(Candidato(3, "DUPLICADO", f"Hay {len(m3)} registro(s) duplicado(s) o posible(s) duplicado(s) por "
                               f"{fmt(A)} USD: podría estar contado de más.", [ctx.ub(r) for r in m3[:5]]))
    fuera = [r for r in recs if r.status in (BLOCKED, PENDING_MAPPING)]
    suma_fuera = sum((r.amount_usd for r in fuera if r.amount_usd is not None), D0)
    sin_valor = [r for r in fuera if r.amount_usd is None]
    if fuera and abs(abs(suma_fuera) - A) <= TOL:
        cands.append(Candidato(4, "REGISTROS_FUERA", f"La suma de los registros bloqueados o pendientes valorables "
                               f"({fmt(suma_fuera)} USD) coincide con el desbalance: están fuera del balance.",
                               [ctx.ub(r) for r in fuera]))
    elif sin_valor:
        cands.append(Candidato(4, "REGISTROS_SIN_VALOR", f"Hay {len(sin_valor)} registro(s) sin valor en USD (no se "
                               f"pueden sumar): no se puede descartar que expliquen el desbalance.",
                               [ctx.ub(r) for r in sin_valor]))
    m5 = []
    for r in valued:
        if not r.account_code or cat[r.account_code].cls not in ("activo", "pasivo", "patrimonio") or \
                r.amount_original is None or r.fx_rate is None:
            continue
        own = to_usd(Decimal(1), ctx.cfg.rates[(r.period, r.currency)]) if (r.period, r.currency) in ctx.cfg.rates \
            else Decimal(1)
        for (p2, c2), fx in sorted(ctx.cfg.rates.items()):
            if (p2, c2) == (r.period, r.currency) or fx.rate <= 0:
                continue
            if abs(abs(r.amount_original * (to_usd(Decimal(1), fx) - own)) - A) <= TOL:
                m5.append((r, c2, p2))
                break
    if m5:
        c = Candidato(5, "DIFERENCIA_DE_TASA", f"El desbalance coincide con valorar un registro con otra tasa: "
                      + "; ".join(f"{r.account_local} ({fmt(r.amount_original)} {r.currency}) con la tasa de {c2} "
                                  f"{p2}" for r, c2, p2 in m5[:3]) + ".", [ctx.ub(r) for r, _c, _p in m5[:5]])
        cands.append(c)
    cercanos = []
    if not cands:
        cercanos = [ctx.ub(r) for r in sorted(valued, key=lambda r: (abs(abs(r.amount_usd) - A), r.source_row))[:3]]
    return D_, cands, cercanos


def _balance(f, ctx, recs):
    cid, p = f.company_id, f.period
    D_, cands, cercanos = diagnosticar_balance(ctx, cid, p)
    if cands:
        c = cands[0]
        causa = (f"Causa candidata más probable (orden determinista): {c.descripcion} Son hipótesis, no certezas; "
                 f"hay {len(cands)} candidata(s) en total.")
    else:
        causa = ("Causa no identificada: ningún registro, duplicado, signo, registro fuera de balance o diferencia de "
                 "tasa coincide con el desbalance. Se muestran los registros más cercanos a D.")
    return (f"{f.message} El balance de {cid} en {p} no cuadra por {fmt(D_)} USD (activo − (pasivo + patrimonio)).",
            abs(D_), False, "El balance no es parte del estado de resultados: no cambia la utilidad, pero indica que "
            "alguna partida de balance está mal o falta.", causa,
            "Revisar las partidas candidatas con la empresa y corregir el archivo de origen."), D_, cands, cercanos


# ------------------------------------------------------------------ discrepancia intercompania
def _fichas_intercompania(ctx: _Ctx) -> List[Ficha]:
    grupos = defaultdict(list)
    for m in ctx.run.matches:
        if m.status != "RECONCILED":
            grupos[(m.period, m.seller_id, m.buyer_id, m.reference)].append(m)
    out = []
    for (p, s, b, ref), ms in sorted(grupos.items(), key=lambda kv: (kv[0][0], kv[0][1], str(kv[0][3]))):
        ids = [i for m in ms for i in m.seller_record_ids + m.buyer_record_ids]
        recs = [ctx.recs[i] for i in ids if i in ctx.recs]
        er = next((m for m in ms if m.statement == "ER"), ms[0])
        dif = abs(er.difference_usd)
        efecto = sum((ctx.sign(r) * r.amount_usd for r in recs
                      if r.amount_usd is not None and ctx.cfg.catalog.get(r.account_code or "")
                      and ctx.cfg.catalog[r.account_code].statement == "ER"), D0)
        afecta = " y ".join("la operación (la venta)" if m.statement == "ER" else
                            "el saldo (cuenta por cobrar y por pagar)" for m in sorted(ms, key=lambda m: m.statement != "ER"))
        out.append(Ficha(
            "", INTERCOMPANIA, NOMBRES[INTERCOMPANIA], "IC-01", "WARN", p, s,
            f"{s} registra {fmt(er.seller_usd)} USD y {b} registra {fmt(er.buyer_usd)} USD (ref. {ref}): diferencia de "
            f"{fmt(er.difference_usd)} USD. La misma diferencia afecta {afecta}; no se elimina ninguna.",
            ctx.ubs(ids),
            f"Ambos lados siguen en el consolidado sin eliminar, por lo que ingresos y costos están brutos por la "
            f"operación y el período queda PROVISIONAL.", dif, False,
            f"La utilidad incluye {efecto:+,.2f} USD de esta operación que desaparecería al conciliar.",
            "Probable diferencia de fecha, de moneda o de tasa, un registro faltante o un importe distinto en una de "
            "las dos empresas.", "Conciliar con ambas empresas antes de eliminar; FinaCore nunca elimina sola una "
            "diferencia."))
    return out


# ------------------------------------------------------------------ orquestacion
def _tipo(f, recs) -> str:
    r = f.rule_id
    if r in ("DUP-01", "DUP-02", "DUP-03", "ARC-01"):
        return DUPLICADO
    if r == "ATI-01":
        return MONEDA_SOSPECHOSA if "Si fuera" in (f.impact or "") else IMPORTE_ATIPICO
    if r == "MON-01":
        motivo = " ".join(recs[0].status_reasons) if recs and recs[0].status_reasons else (f.message or "")
        if "Moneda faltante" in motivo:
            return MONEDA_FALTANTE
        if "invalida o desconocida" in motivo:
            return MONEDA_NO_RECONOCIDA
        return TASA_INVALIDA
    if r == "ING-01":
        return NO_NUMERICO
    return {"FEC-01": FECHA, "TOT-01": TOTAL_DESC, "BAL-01": BALANCE, "MAP-01": SIN_MAPEAR, "SIGN-01": SIGNO,
            "MES-01": MES_FALTANTE, "CARGA-01": CARGA, "TAS-01": TASA_SOSPECHOSA,
            "REE-01": REENVIO, "REE-02": REENVIO}.get(r, OTRO)


_BUILDERS = {DUPLICADO: _dup, MONEDA_SOSPECHOSA: _moneda_sospechosa, MONEDA_NO_RECONOCIDA: _moneda_no_reconocida,
             MONEDA_FALTANTE: _moneda_faltante, TASA_INVALIDA: _tasa_invalida, TASA_SOSPECHOSA: _tasa_sospechosa,
             SIN_MAPEAR: _sin_mapear, FECHA: _fecha, TOTAL_DESC: _total, SIGNO: _signo, MES_FALTANTE: _mes,
             CARGA: _carga, NO_NUMERICO: _no_numerico, REENVIO: _reenvio}


def _donde_sin_registros(f, ctx) -> List[Ubicacion]:
    """MES-01 / ARC-01 / CARGA-01 no apuntan a filas: se ubican por empresa y archivo."""
    cos = [c for c in ctx.cfg.companies.values() if c.file in (f.message or "")] or \
        [c for c in ctx.cfg.companies.values() if c.company_id == f.company_id]
    return [Ubicacion(c.company_id, c.file, None, None, f.period, None, None, None, None) for c in cos]


def diagnosticar(run) -> List[Ficha]:
    """Una ficha por hallazgo (las discrepancias intercompania se unen: operacion y saldo en una sola)."""
    ctx = _Ctx(run)
    out: List[Ficha] = []
    for f in run.findings:
        if f.rule_id == "IC-01":
            continue                                           # se arman desde run.matches, una por discrepancia
        recs = [ctx.recs[i] for i in f.record_ids if i in ctx.recs]
        tipo = _tipo(f, recs)
        donde = ctx.ubs(f.record_ids) or _donde_sin_registros(f, ctx)
        cands, cercanos, dif = [], [], None
        if tipo == BALANCE:
            (imp, usd, est, util, causa, acc), dif, cands, cercanos = _balance(f, ctx, recs)
        elif tipo in _BUILDERS:
            imp, usd, est, util, causa, acc = _BUILDERS[tipo](f, ctx, recs) if tipo != DUPLICADO else _dup(f, ctx, recs)
        else:
            imp, usd, est, util, causa, acc = _ficha_generica(f, ctx, recs, tipo)
        out.append(Ficha("", tipo, NOMBRES[tipo], f.rule_id, f.severity, f.period, f.company_id, f.message, donde,
                         imp, usd, est, util, causa, acc, cands, cercanos, dif,
                         (bool(cands) if tipo == BALANCE else None)))
    out.extend(_fichas_intercompania(ctx))
    out.sort(key=lambda x: (x.impacto_usd is None, -(x.impacto_usd or D0), x.tipo, x.period or "", x.company_id or ""))
    for i, f in enumerate(out, 1):
        f.ficha_id = f"FCH-{i:03d}"
    return out


def contador_por_tipo(fichas: List[Ficha]) -> Dict[str, int]:
    c: Dict[str, int] = defaultdict(int)
    for f in fichas:
        c[f.tipo] += 1
    return dict(sorted(c.items(), key=lambda kv: (-kv[1], kv[0])))
