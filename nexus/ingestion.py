"""Lectura de XLSX/CSV/JSON a registros normalizados con origen (archivo, hoja, fila).

Generico: detecta codificacion, separador, fila de encabezado, separador decimal y hojas sin tabla.
Nada se descarta en silencio: un dato invalido queda como registro BLOCKED con su motivo.
"""
import csv
import io
import json
from pathlib import Path
from typing import List, Optional, Tuple

from openpyxl import load_workbook

from .mapping import header_score, map_account, map_counterparty, map_headers
from .schemas import BLOCKED, PENDING_MAPPING, TOTAL, GroupConfig, Record
from .text import blank, detect_decimal_sep, parse_amount, parse_period

MAX_HEADER_SCAN = 20
FILE_CURRENCY_KEYS = {"currency", "moneda", "reporting currency", "moneda de reporte", "divisa"}


# ------------------------------------------------------------------ lectura cruda: tablas
class Table:
    def __init__(self, sheet: Optional[str], header: List, rows: List[Tuple[int, List]], meta=None):
        self.sheet, self.header, self.rows, self.meta = sheet, header, rows, meta or {}


def _find_header(grid: List[Tuple[int, List]]):
    for i, (_, cells) in enumerate(grid[:MAX_HEADER_SCAN]):
        if header_score(cells) >= 2:
            return i
    return None


def read_xlsx(path) -> List[Table]:
    wb = load_workbook(path, data_only=True, read_only=True)
    out = []
    for ws in wb.worksheets:
        grid = [(i, list(r)) for i, r in enumerate(ws.iter_rows(values_only=True), start=1)]
        h = _find_header(grid)
        if h is None:
            continue                                   # hoja de notas, portada, etc.
        out.append(Table(ws.title, grid[h][1], [g for g in grid[h + 1:] if any(not blank(c) for c in g[1])]))
    return out


def _decode(path) -> str:
    data = Path(path).read_bytes()
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"No se pudo decodificar {path}")


def read_csv(path) -> List[Table]:
    text = _decode(path)
    sample = "\n".join(text.splitlines()[:20])
    try:
        delim = csv.Sniffer().sniff(sample, delimiters=";,\t|").delimiter
    except csv.Error:
        delim = ","
    grid = [(i, r) for i, r in enumerate(csv.reader(io.StringIO(text), delimiter=delim), start=1)]
    h = _find_header(grid)
    if h is None:
        return []
    return [Table(None, grid[h][1], [g for g in grid[h + 1:] if any(not blank(c) for c in g[1])])]


def read_json(path) -> List[Table]:
    doc = json.loads(_decode(path))
    if isinstance(doc, list):
        items, meta = doc, {}
    else:
        key = next((k for k, v in doc.items() if isinstance(v, list) and v and isinstance(v[0], dict)), None)
        if key is None:
            return []
        items, meta = doc[key], {k: v for k, v in doc.items() if not isinstance(v, (list, dict))}
    header = list(dict.fromkeys(k for it in items for k in it))
    rows = [(i, [it.get(k) for k in header]) for i, it in enumerate(items, start=1)]
    sheet = None if isinstance(doc, list) else key
    return [Table(sheet, header, rows, meta)]


READERS = {".xlsx": read_xlsx, ".xlsm": read_xlsx, ".csv": read_csv, ".txt": read_csv, ".json": read_json}


# ------------------------------------------------------------------ normalizacion
def _file_currency(meta) -> Optional[str]:
    from .text import norm
    for k, v in meta.items():
        if norm(k) in FILE_CURRENCY_KEYS and not blank(v):
            return str(v).strip().upper()
    return None


def ingest_file(path, company_id: str, cfg: GroupConfig) -> List[Record]:
    path = Path(path)
    reader = READERS.get(path.suffix.lower())
    if reader is None:
        raise ValueError(f"Formato no soportado: {path.name}")
    company = cfg.companies[company_id]
    records = []
    for t in reader(path):
        mapping, _unmapped = map_headers(t.header)
        idx = {f: t.header.index(col) for col, f in mapping.items()}
        has_cur_col = "currency" in idx
        file_cur = _file_currency(t.meta)
        dec = detect_decimal_sep(r[1][idx["amount"]] for r in t.rows if idx["amount"] < len(r[1]))

        def cell(cells, f):
            i = idx.get(f)
            return cells[i] if i is not None and i < len(cells) else None

        for row_no, cells in t.rows:
            raw = {str(t.header[i]): v for i, v in enumerate(cells) if i < len(t.header)}
            rec = Record(record_id=f"{company_id}|{path.name}|{t.sheet or ''}|{row_no}", company_id=company_id,
                         source_file=path.name, source_sheet=t.sheet, source_row=row_no, raw=raw)
            rec.period, rec.date = parse_period(cell(cells, "period"))
            if rec.period is None:
                rec.block(BLOCKED, f"Periodo invalido o vacio: {cell(cells, 'period')!r}")
            rec.amount_original = parse_amount(cell(cells, "amount"), dec)
            if rec.amount_original is None:
                rec.block(BLOCKED, f"Importe no numerico o vacio: {cell(cells, 'amount')!r}")
            # moneda: columna explicita > moneda del archivo > configuracion de la empresa
            if has_cur_col:
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


def ingest_group(input_dir, cfg: GroupConfig) -> List[Record]:
    """Lee el archivo de cada empresa segun empresas.csv. Archivo faltante -> error explicito."""
    d = Path(input_dir)
    out = []
    for c in cfg.companies.values():
        p = d / c.file
        if not p.exists():
            raise FileNotFoundError(f"Falta el archivo de {c.company_id}: {p}")
        out.extend(ingest_file(p, c.company_id, cfg))
    return out
