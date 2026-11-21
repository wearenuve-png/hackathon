from typing import List, Optional

from openpyxl import load_workbook

from ..schemas import CompanyProfile
from ..text import blank
from .base import SourceAdapter, Table, find_header_row, header_gap


class ExcelAdapter(SourceAdapter):
    source_type = "xlsx"

    def extract(self, path, profile: Optional[CompanyProfile] = None) -> List[Table]:
        wb = load_workbook(path, data_only=True, read_only=True)
        out = []
        for ws in wb.worksheets:
            grid = [(i, list(r)) for i, r in enumerate(ws.iter_rows(values_only=True), start=1)]
            h = find_header_row(grid, profile)
            if h is None:
                if profile is not None and ws.title in profile.sheets:
                    self.gaps[ws.title] = header_gap(grid, profile)
                continue                                   # hoja de notas, portada, etc.
            out.append(Table(ws.title, grid[h][1], [g for g in grid[h + 1:] if any(not blank(c) for c in g[1])]))
        return out
