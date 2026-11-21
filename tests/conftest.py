"""Fixtures comunes. Los valores esperados salen SIEMPRE de tests/fixtures/answer_key.json."""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "synthetic"
KEY = json.loads((ROOT / "tests" / "fixtures" / "answer_key.json").read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def _registro_de_aprobaciones_aislado(tmp_path_factory, monkeypatch):
    """Ninguna prueba escribe ni lee el registro real de aprobaciones (data/output/aprobaciones.jsonl)."""
    monkeypatch.setenv("NEXUS_APROBACIONES", str(tmp_path_factory.mktemp("aprob") / "aprobaciones.jsonl"))
    monkeypatch.setenv("NEXUS_MANIFIESTOS", str(tmp_path_factory.mktemp("manif")))
    monkeypatch.setenv("NEXUS_CARGA", str(tmp_path_factory.mktemp("carga")))


@pytest.fixture(autouse=True)
def _sin_llave_del_asistente(monkeypatch):
    """El Asistente esta apagado por defecto: ninguna prueba hereda una llave real del entorno."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


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


@pytest.fixture()
def built_profiles(cfg, tmp_path):
    """Perfiles generados a una carpeta temporal con la misma logica de scripts/build_profiles.py."""
    import csv
    from nexus import ingestion
    from nexus.profiles import build_profile, save_profile
    names = {}
    with open(DATA / "equivalencias.csv", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            names.setdefault(r["company_id"], {})[r["cuenta_local"]] = r["account_code"]
    types = {".xlsx": "xlsx", ".csv": "csv", ".json": "json"}
    for c in cfg.companies.values():
        p = DATA / c.file
        tables = ingestion.READERS[p.suffix.lower()](p)
        save_profile(build_profile(c, tables, names[c.company_id], types[p.suffix.lower()],
                                   approved_by="Tester"), tmp_path)
    return tmp_path


@pytest.fixture()
def data_copy(tmp_path):
    """Copia editable del dataset sintetico (los tests nunca tocan data/synthetic)."""
    import shutil
    d = tmp_path / "data"
    shutil.copytree(DATA, d, ignore=shutil.ignore_patterns("generate.py", "README_SINTETICO.md"))
    return d
