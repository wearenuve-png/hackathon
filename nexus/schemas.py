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
    debit: Optional[Decimal] = None              # solo si la fuente trae debito/credito
    credit: Optional[Decimal] = None

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
    nature: Optional[str] = None  # "D" (deudora) / "C" (acreedora); por defecto segun la clase


SUPPORTED_PROFILE_SCHEMA = 1
SOURCE_TYPES = {"xlsx", "csv", "json"}
SIGN_SIGNED = "signed_amount"
SIGN_DEBIT_CREDIT = "debit_credit"
CURRENCY_MODES = {"column", "file_key", "company_config"}


@dataclass
class SourceSpec:
    type: str                      # xlsx / csv / json
    file: str


@dataclass
class CompanyProfile:
    """Como interpretar la fuente de UNA empresa. Se valida, se versiona y registra quien lo aprobo."""
    company_id: str
    company_name: str
    country: str
    functional_currency: str
    source: SourceSpec
    columns: Dict[str, str]                        # campo canonico -> encabezado exacto en la fuente
    accounts: Dict[str, str]                       # cuenta local -> codigo del catalogo comun
    sheets: List[str] = field(default_factory=list)  # hojas/secciones que deben existir
    sign_convention: str = SIGN_SIGNED
    currency_mode: str = "company_config"
    currency_key: Optional[str] = None             # encabezado (column) o clave (file_key)
    counterparty_aliases: List[str] = field(default_factory=list)
    schema_version: int = SUPPORTED_PROFILE_SCHEMA
    profile_version: int = 1
    approval_status: str = "PENDING"               # APPROVED / PENDING
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    profile_hash: str = ""


@dataclass
class LoadReport:
    """Resultado de la ultima carga de una empresa frente a su perfil."""
    company_id: str
    file: str
    status: str                                    # MATCHED / REVIEW / AUTO (sin perfiles)
    profile_version: Optional[int] = None
    approval_status: Optional[str] = None
    reasons: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    n_records: int = 0


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
    profiles: Dict[str, "CompanyProfile"] = field(default_factory=dict)


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
class ImpactRange:
    """Efecto en utilidad neta de un registro que quedo fuera. No modifica ninguna cifra."""
    record_id: str
    company_id: str
    period: str
    account_local: Optional[str]
    utility_excluded: Decimal                 # tal como esta el consolidado (el registro no cuenta)
    utility_as_is: Optional[Decimal]          # si se incluyera tal como viene (None = no calculable)
    utility_corrected: Optional[Decimal]      # si se corrigiera segun la hipotesis de 'note'
    utility_low: Decimal
    utility_high: Decimal
    note: str


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
    impact_ranges: List[ImpactRange] = field(default_factory=list)
    utility_range: Optional[Tuple[Decimal, Decimal]] = None   # rango de utilidad neta si todo se resolviera


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
    load_reports: Dict[str, "LoadReport"] = field(default_factory=dict)
