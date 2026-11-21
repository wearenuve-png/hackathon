"""Fixtures comunes. Los valores esperados salen SIEMPRE de tests/fixtures/answer_key.json."""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "synthetic"
KEY = json.loads((ROOT / "tests" / "fixtures" / "answer_key.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def key():
    return KEY


@pytest.fixture(scope="session")
def cfg():
    from nexus.config import load_group_config
    return load_group_config(DATA, ic_tolerance_usd=KEY["tolerancia_intercompania_usd"])


@pytest.fixture()
def records(cfg):
    from nexus.ingestion import ingest_group
    return ingest_group(DATA, cfg)


def find(records, loc):
    """Registro en la ubicacion (archivo, hoja, fila) que indica la clave."""
    hits = [r for r in records if r.source_file == loc["file"] and r.source_sheet == loc.get("sheet")
            and r.source_row == loc["row"]]
    assert len(hits) == 1, f"No se encontro exactamente un registro en {loc}"
    return hits[0]
