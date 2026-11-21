"""Naturaleza contable de una cuenta (deudora o acreedora), para fuentes con debito/credito."""
from .schemas import GroupConfig

DEBIT_CLASSES = {"activo", "costo", "gasto_operativo", "gasto_financiero", "impuesto"}


def nature(code: str, cfg: GroupConfig) -> str:
    """'D' o 'C'. Usa la columna `naturaleza` del catalogo si existe; si no, la deriva de la clase.
    Una cuenta de total hereda la naturaleza de sus componentes."""
    acc = cfg.catalog[code]
    if acc.nature in ("D", "C"):
        return acc.nature
    cls = acc.cls
    if cls == "total" and acc.total_of:
        return nature(acc.total_of[0], cfg)
    return "D" if cls in DEBIT_CLASSES else "C"
