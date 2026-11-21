"""Lectura de XLSX/CSV/JSON a registros normalizados con origen."""
from typing import List
from .schemas import GroupConfig, Record


def ingest_file(path, company_id: str, cfg: GroupConfig) -> List[Record]:
    raise NotImplementedError


def ingest_group(input_dir, cfg: GroupConfig) -> List[Record]:
    raise NotImplementedError
