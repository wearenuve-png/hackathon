"""Utilidades de texto, numeros y fechas. Sin conocimiento de ningun dataset."""
import datetime as dt
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from typing import Iterable, Optional


def norm(s) -> str:
    """'Período ' -> 'periodo'; 'No. Factura' -> 'no factura'; 'cia_relacionada' -> 'cia relacionada'."""
    if s is None:
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return s.strip()


def blank(v) -> bool:
    return v is None or (isinstance(v, str) and v.strip() == "")


def detect_decimal_sep(values: Iterable) -> str:
    """Decide si una columna de texto usa ',' o '.' como separador decimal."""
    comma = dot = 0
    for v in values:
        if not isinstance(v, str):
            continue
        t = v.strip()
        if re.search(r",\d{1,2}$", t):
            comma += 1
        elif re.search(r"\.\d{1,2}$", t):
            dot += 1
    return "," if comma > dot else "."


def parse_amount(v, decimal_sep: str = ".") -> Optional[Decimal]:
    if blank(v) or isinstance(v, bool):
        return None
    if isinstance(v, (int, float, Decimal)):
        return Decimal(str(v))
    t = str(v).strip().replace(" ", "").replace(" ", "")
    neg = t.startswith("(") and t.endswith(")")
    t = t.strip("()")
    if decimal_sep == ",":
        t = t.replace(".", "").replace(",", ".")
    else:
        t = t.replace(",", "")
    if not re.fullmatch(r"[-+]?\d+(\.\d+)?", t):
        return None
    try:
        d = Decimal(t)
    except InvalidOperation:
        return None
    return -d if neg else d


MONTHS = {"ene": 1, "jan": 1, "feb": 2, "mar": 3, "abr": 4, "apr": 4, "may": 5, "jun": 6, "jul": 7,
          "ago": 8, "aug": 8, "sep": 9, "set": 9, "oct": 10, "nov": 11, "dic": 12, "dec": 12}


def parse_period(v):
    """-> (periodo 'YYYY-MM' o None, fecha completa o None)."""
    if blank(v):
        return None, None
    if isinstance(v, dt.datetime):
        return f"{v.year:04d}-{v.month:02d}", v.date()
    if isinstance(v, dt.date):
        return f"{v.year:04d}-{v.month:02d}", v
    t = str(v).strip()
    m = re.fullmatch(r"(\d{4})-(\d{1,2})(?:-(\d{1,2}))?(?:[ T].*)?", t)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), m.group(3)
        return _ok(y, mo, int(d) if d else None)
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", t)          # dd/mm/aaaa
    if m:
        return _ok(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    m = re.fullmatch(r"(\d{1,2})/(\d{4})", t)                     # mm/aaaa
    if m:
        return _ok(int(m.group(2)), int(m.group(1)), None)
    m = re.fullmatch(r"([A-Za-z]{3})[a-z]*\.?[\s\-/]+(\d{4})", t)  # Oct 2026, dic-2026
    if m and m.group(1).lower() in MONTHS:
        return _ok(int(m.group(2)), MONTHS[m.group(1).lower()], None)
    return None, None


def _ok(y, mo, d):
    if not 1 <= mo <= 12:
        return None, None
    try:
        date = dt.date(y, mo, d) if d else None
    except ValueError:
        return None, None
    return f"{y:04d}-{mo:02d}", date
