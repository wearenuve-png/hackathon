"""Conciliacion intercompania. Solo se elimina lo conciliado."""
from typing import List, Tuple
from .schemas import Adjustment, GroupConfig, ICMatch, Record


def match(records: List[Record], cfg: GroupConfig) -> List[ICMatch]:
    raise NotImplementedError


def eliminations(matches: List[ICMatch], records: List[Record]) -> List[Adjustment]:
    raise NotImplementedError
