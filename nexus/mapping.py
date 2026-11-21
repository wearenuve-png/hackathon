"""Homologacion de encabezados, cuentas y contrapartes."""
from typing import Dict, List, Optional, Tuple
from .schemas import GroupConfig, Record


def map_headers(columns: List[str]) -> Tuple[Dict[str, str], List[str]]:
    """-> ({columna_original: campo_canonico}, columnas_sin_mapear)"""
    raise NotImplementedError


def map_account(company_id: str, local_name: str, cfg: GroupConfig) -> Optional[str]:
    raise NotImplementedError


def map_counterparty(text: str, cfg: GroupConfig) -> Optional[str]:
    raise NotImplementedError
