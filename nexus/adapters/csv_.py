import csv
import io
from pathlib import Path
from typing import List, Optional

from ..schemas import CompanyProfile
from ..text import blank
from .base import SourceAdapter, Table, find_header_row, header_gap


def decode(path) -> str:
    data = Path(path).read_bytes()
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"No se pudo decodificar {path}")


class CsvAdapter(SourceAdapter):
    source_type = "csv"

    def extract(self, path, profile: Optional[CompanyProfile] = None) -> List[Table]:
        text = decode(path)
        sample = "\n".join(text.splitlines()[:20])
        try:
            delim = csv.Sniffer().sniff(sample, delimiters=";,\t|").delimiter
        except csv.Error:
            delim = ","
        grid = [(i, r) for i, r in enumerate(csv.reader(io.StringIO(text), delimiter=delim), start=1)]
        h = find_header_row(grid, profile)
        if h is None:
            if profile is not None:
                self.gaps[""] = header_gap(grid, profile)
            return []
        return [Table(None, grid[h][1], [g for g in grid[h + 1:] if any(not blank(c) for c in g[1])])]
