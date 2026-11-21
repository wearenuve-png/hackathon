"""Clase base de los adaptadores de fuente.

Un adaptador hace dos cosas, y solo dos:
  extract(path, profile)   -> lista de Table (encabezado + filas con su numero de fila de origen)
  normalize(tables, ...)   -> lista de Record en el esquema canonico (compartido por todos los formatos)

Con perfil, la fuente debe coincidir con lo que el perfil declara; si no coincide se lanza
ProfileMismatch y la carga queda en revision (nunca se procesa en silencio con un mapeo incorrecto).
Sin perfil se usa deteccion automatica (modo legado / onboarding).
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple

from ..mapping import file_currency_key, header_score, map_account, map_counterparty, map_headers
from ..schemas import BLOCKED, PENDING_MAPPING, TOTAL, CompanyProfile, GroupConfig, Record
from ..text import blank, detect_decimal_sep, norm, parse_amount, parse_period

MAX_HEADER_SCAN = 20


class ProfileMismatch(Exception):
    def __init__(self, reasons: List[str]):
        self.reasons = reasons
        super().__init__("; ".join(reasons))


class Table:
    def __init__(self, sheet: Optional[str], header: List, rows: List[Tuple[int, List]], meta=None):
        self.sheet, self.header, self.rows, self.meta = sheet, header, rows, meta or {}


def find_header_row(grid: List[Tuple[int, List]], profile: Optional[CompanyProfile] = None) -> Optional[int]:
    if profile is None:
        for i, (_, cells) in enumerate(grid[:MAX_HEADER_SCAN]):
            if header_score(cells) >= 2:
                return i
        return None
    want = {norm(h) for h in profile.columns.values()}
    for i, (_, cells) in enumerate(grid[:MAX_HEADER_SCAN]):
        if want <= {norm(c) for c in cells if c is not None}:
            return i
    return None


def header_gap(grid, profile: CompanyProfile) -> List[str]:
    """Encabezados del perfil que faltan en la fila que mas se le parece."""
    want = {norm(h): h for h in profile.columns.values()}
    best = None
    for _, cells in grid[:MAX_HEADER_SCAN]:
        have = {norm(c) for c in cells if c is not None}
        missing = [h for n, h in want.items() if n not in have]
        if best is None or len(missing) < len(best):
            best = missing
    return best if best is not None else list(want.values())


class SourceAdapter(ABC):
    source_type = ""

    def __init__(self):
        self.gaps: Dict[str, List[str]] = {}          # hoja -> encabezados faltantes (modo perfil)

    # ---- 1) extraer
    @abstractmethod
    def extract(self, path, profile: Optional[CompanyProfile] = None) -> List[Table]:
        ...

    # ---- plantilla
    def ingest(self, path, company_id: str, cfg: GroupConfig,
               profile: Optional[CompanyProfile] = None) -> Tuple[List[Record], List[str]]:
        self.gaps = {}
        tables = self.extract(path, profile)
        notes: List[str] = []
        if profile is not None:
            self.check_profile(tables, profile)
            declared = {norm(h) for h in profile.columns.values()}
            extra = sorted({str(h) for t in tables for h in t.header if h is not None and norm(h)
                            and norm(h) not in declared})
            if extra:
                notes.append("Columnas no declaradas en el perfil (se ignoran): " + ", ".join(extra))
        return self.normalize(tables, path, company_id, cfg, profile), notes

    def check_profile(self, tables: List[Table], profile: CompanyProfile) -> None:
        reasons = []
        if not tables:
            falt = sorted({h for g in self.gaps.values() for h in g}) or list(profile.columns.values())
            reasons.append("Ninguna tabla del archivo coincide con el perfil: faltan los encabezados "
                           + ", ".join(repr(h) for h in falt))
        else:
            found = {t.sheet for t in tables}
            missing = [s for s in profile.sheets if s not in found]
            if missing:
                reasons.append("Faltan hojas/secciones declaradas en el perfil: " + ", ".join(missing))
                for s in missing:
                    if self.gaps.get(s):
                        reasons.append(f"  en '{s}' faltan los encabezados: " + ", ".join(self.gaps[s]))
        if profile.currency_mode == "file_key" and tables and not any(
                file_currency_key(t.meta) == profile.currency_key for t in tables):
            reasons.append(f"Falta la clave de moneda {profile.currency_key!r} declarada en el perfil")
        if reasons:
            raise ProfileMismatch(reasons)

    # ---- 2) normalizar (igual para todos los formatos)
    def normalize(self, tables: List[Table], path, company_id: str, cfg: GroupConfig,
                  profile: Optional[CompanyProfile] = None) -> List[Record]:
        name = getattr(path, "name", str(path))
        company = cfg.companies[company_id]
        records: List[Record] = []
        for t in tables:
            norm_header = [norm(h) for h in t.header]
            if profile is not None:
                idx = {f: norm_header.index(norm(h)) for f, h in profile.columns.items()}
                cur_mode = profile.currency_mode
            else:
                mapping, _ = map_headers(t.header)
                idx = {f: t.header.index(col) for col, f in mapping.items()}
                cur_mode = "column" if "currency" in idx else None
            file_cur = None
            if profile is not None and cur_mode == "file_key":
                v = next((m for k, m in t.meta.items() if k == profile.currency_key), None)
                file_cur = None if blank(v) else str(v).strip().upper()
            elif profile is None:
                k = file_currency_key(t.meta)
                file_cur = str(t.meta[k]).strip().upper() if k else None
            dec = detect_decimal_sep(r[1][idx["amount"]] for r in t.rows if idx["amount"] < len(r[1]))

            def cell(cells, f):
                i = idx.get(f)
                return cells[i] if i is not None and i < len(cells) else None

            for row_no, cells in t.rows:
                raw = {str(t.header[i]): v for i, v in enumerate(cells) if i < len(t.header)}
                rec = Record(record_id=f"{company_id}|{name}|{t.sheet or ''}|{row_no}", company_id=company_id,
                             source_file=name, source_sheet=t.sheet, source_row=row_no, raw=raw)
                rec.period, rec.date = parse_period(cell(cells, "period"))
                if rec.period is None:
                    rec.block(BLOCKED, f"Periodo invalido o vacio: {cell(cells, 'period')!r}")
                rec.amount_original = parse_amount(cell(cells, "amount"), dec)
                if rec.amount_original is None:
                    rec.block(BLOCKED, f"Importe no numerico o vacio: {cell(cells, 'amount')!r}")
                # moneda: columna explicita > moneda del archivo > configuracion de la empresa
                if cur_mode == "column":
                    v = cell(cells, "currency")
                    rec.currency = None if blank(v) else str(v).strip().upper()
                    rec.currency_source = "COLUMN"
                else:
                    rec.currency = file_cur or company.currency
                    rec.currency_source = "FILE" if file_cur else "COMPANY_CONFIG"
                acc = cell(cells, "account")
                rec.account_local = None if blank(acc) else str(acc).strip()
                rec.description = None if blank(cell(cells, "description")) else str(cell(cells, "description"))
                tx = cell(cells, "transaction_id")
                rec.transaction_id = None if blank(tx) else str(tx).strip()
                cp = cell(cells, "counterparty")
                rec.counterparty_text = None if blank(cp) else str(cp).strip()
                rec.counterparty_id = map_counterparty(rec.counterparty_text, cfg) if rec.counterparty_text else None
                if rec.counterparty_id == company_id:
                    rec.counterparty_id = None
                code = map_account(company_id, rec.account_local, cfg) if rec.account_local else None
                if code is None:
                    rec.block(PENDING_MAPPING, f"Cuenta sin equivalencia en el catalogo: {rec.account_local!r}")
                else:
                    rec.account_code, rec.mapping_status = code, "CONFIRMED"
                    acc_def = cfg.catalog.get(code)
                    if acc_def and acc_def.cls == "total":
                        rec.is_total = True
                        if rec.status == "OK":
                            rec.status = TOTAL
                records.append(rec)
        return records
