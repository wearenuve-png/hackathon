"""Contrato de datos de NEXUS. Se cambia solo avisando al equipo.

Reglas: dinero siempre Decimal; el dato original nunca se pierde (raw, source_*).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
import datetime as dt

# ---- estados de un registro
OK = "OK"                                  # entra al consolidado
BLOCKED = "BLOCKED"                        # no entra: dato invalido (moneda, signo, importe, periodo)
PENDING_MAPPING = "PENDING_MAPPING"        # no entra hasta confirmar la cuenta
EXCLUDED_DUPLICATE = "EXCLUDED_DUPLICATE"  # excluido por ajuste registrado (reversible)
TOTAL = "TOTAL"                            # fila de total: se verifica, nunca se suma
INCLUDED_STATUSES = {OK}

# ---- banderas (no excluyen)
FLAG_POSSIBLE_DUPLICATE = "POSSIBLE_DUPLICATE"
FLAG_ATYPICAL = "ATYPICAL"
FLAG_IC_DISCREPANCY = "IC_DISCREPANCY"
FLAG_IC_UNMATCHED = "IC_UNMATCHED"

# ---- orientacion de tasa
USD_PER_LOCAL = "USD_PER_LOCAL"   # se multiplica (convencion del grupo)
LOCAL_PER_USD = "LOCAL_PER_USD"   # se divide

# ---- severidad de hallazgos
BLOCK, WARN, INFO = "BLOCK", "WARN", "INFO"


@dataclass
class Record:
    record_id: str
    company_id: str
    source_file: str
    source_sheet: Optional[str]
    source_row: int
    raw: Dict[str, object]                       # celdas originales, sin tocar
    period: Optional[str] = None                 # YYYY-MM
    date: Optional[dt.date] = None
    account_local: Optional[str] = None
    account_code: Optional[str] = None
    mapping_status: str = "PENDING"              # CONFIRMED / PENDING
    amount_original: Optional[Decimal] = None
    currency: Optional[str] = None
    currency_source: Optional[str] = None        # COLUMN / FILE / COMPANY_CONFIG
    counterparty_text: Optional[str] = None
    counterparty_id: Optional[str] = None        # solo si es empresa del grupo
    transaction_id: Optional[str] = None
    description: Optional[str] = None
    is_total: bool = False
    fx_rate: Optional[Decimal] = None
    fx_orientation: Optional[str] = None
    amount_usd: Optional[Decimal] = None
    status: str = OK
    status_reasons: List[str] = field(default_factory=list)
    flags: List[str] = field(default_factory=list)
    ic_match_id: Optional[str] = None
    adjustment_ids: List[str] = field(default_factory=list)

    def block(self, status: str, reason: str) -> None:
        """El primer estado no-OK manda; los motivos se acumulan."""
        if self.status == OK:
            self.status = status
        self.status_reasons.append(reason)


@dataclass
class FxRate:
    period: str
    currency: str
    rate: Decimal
    orientation: str = USD_PER_LOCAL


@dataclass
class Company:
    company_id: str
    name: str
    country: str
    currency: str
    file: str
    aliases: List[str]


@dataclass
class Account:
    code: str
    name: str
    statement: str                # ER / BG
    cls: str                      # ingreso, costo, gasto_operativo, ..., activo, pasivo, patrimonio, total
    current: Optional[bool] = None
    total_of: List[str] = field(default_factory=list)


@dataclass
class GroupConfig:
    companies: Dict[str, Company]
    rates: Dict[Tuple[str, str], FxRate]          # (period, currency) -> tasa
    catalog: Dict[str, Account]
    equivalences: Dict[Tuple[str, str], str]      # (company_id, cuenta_local normalizada) -> code
    periods: Dict[str, str]                       # period -> real / presupuesto
    base_currency: str = "USD"
    ic_tolerance_usd: Decimal = Decimal("1.00")
    rules_version: str = "nexus-rules-0.1"


@dataclass
class Finding:
    finding_id: str
    rule_id: str
    severity: str
    message: str
    record_ids: List[str] = field(default_factory=list)
    period: Optional[str] = None
    company_id: Optional[str] = None
    found: Optional[str] = None
    expected: Optional[str] = None
    suggestion: str = ""
    impact: Optional[str] = None


@dataclass
class Adjustment:
    adjustment_id: str
    kind: str                     # DUPLICATE_EXCLUSION / IC_ELIMINATION
    record_ids: List[str]
    amount_usd: Decimal           # efecto sobre el consolidado (negativo = resta)
    account_code: Optional[str]
    period: Optional[str]
    reason: str
    rule: str
    reversible: bool = True
    approved_by: str = "regla automatica"


@dataclass
class ICMatch:
    match_id: str
    period: str
    statement: str                # ER (operacion) / BG (saldo)
    seller_id: str
    buyer_id: str
    reference: Optional[str]
    seller_record_ids: List[str]
    buyer_record_ids: List[str]
    seller_usd: Decimal
    buyer_usd: Decimal
    status: str                   # RECONCILED / DISCREPANCY / UNMATCHED

    @property
    def difference_usd(self) -> Decimal:
        return self.seller_usd - self.buyer_usd


@dataclass
class ConsolidatedLine:
    period: str
    account_code: str
    amount_usd: Decimal
    gross_usd: Decimal                         # antes de eliminaciones
    record_ids: List[str] = field(default_factory=list)
    adjustment_ids: List[str] = field(default_factory=list)


@dataclass
class ExcludedItem:
    record_id: str
    company_id: str
    period: Optional[str]
    status: str
    reasons: List[str]
    amount_original: Optional[Decimal]
    currency: Optional[str]
    amount_usd: Optional[Decimal]              # None si no se puede convertir


@dataclass
class PeriodResult:
    period: str
    kind: str                                  # real / presupuesto
    lines: Dict[str, ConsolidatedLine]
    summary: Dict[str, Decimal]
    naive_summary: Dict[str, Decimal]
    excluded: List[ExcludedItem]
    excluded_usd_by_status: Dict[str, Decimal]
    excluded_not_convertible: int
    missing_companies: List[str]
    provisional: bool
    provisional_reasons: List[str]


@dataclass
class RunResult:
    run_id: str
    config: GroupConfig
    records: List[Record]
    adjustments: List[Adjustment]
    matches: List[ICMatch]
    findings: List[Finding]
    periods: Dict[str, PeriodResult]
    input_hashes: Dict[str, str]
