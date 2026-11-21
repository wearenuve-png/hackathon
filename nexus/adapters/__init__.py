from .base import ProfileMismatch, SourceAdapter, Table
from .csv_ import CsvAdapter
from .excel import ExcelAdapter
from .json_ import JsonAdapter

ADAPTERS = {"xlsx": ExcelAdapter, "csv": CsvAdapter, "json": JsonAdapter}
EXT_TYPE = {".xlsx": "xlsx", ".xlsm": "xlsx", ".csv": "csv", ".txt": "csv", ".json": "json"}


def adapter_for(source_type: str) -> SourceAdapter:
    try:
        return ADAPTERS[source_type]()
    except KeyError:
        raise ValueError(f"Sin adaptador para el tipo de fuente {source_type!r}")
