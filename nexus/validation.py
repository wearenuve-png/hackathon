"""Reglas de validacion. Las que cambian el estado de un registro corren antes de consolidar."""
from typing import List, Tuple
from .schemas import Adjustment, Finding, GroupConfig, Record


def apply_record_rules(records: List[Record], cfg: GroupConfig) -> Tuple[List[Adjustment], List[Finding]]:
    raise NotImplementedError


def validate(records: List[Record], cfg: GroupConfig) -> List[Finding]:
    raise NotImplementedError
