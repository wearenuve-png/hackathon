import json
from typing import List, Optional

from ..schemas import CompanyProfile
from ..text import norm
from .base import SourceAdapter, Table
from .csv_ import decode


class JsonAdapter(SourceAdapter):
    source_type = "json"

    def extract(self, path, profile: Optional[CompanyProfile] = None) -> List[Table]:
        doc = json.loads(decode(path))
        if isinstance(doc, list):
            items, meta, sheet = doc, {}, None
        else:
            key = next((k for k, v in doc.items() if isinstance(v, list) and v and isinstance(v[0], dict)), None)
            if key is None:
                if profile is not None:
                    self.gaps[""] = list(profile.columns.values())
                return []
            items, meta, sheet = doc[key], {k: v for k, v in doc.items() if not isinstance(v, (list, dict))}, key
        header = list(dict.fromkeys(k for it in items for k in it))
        if profile is not None:
            have = {norm(h) for h in header}
            missing = [h for h in profile.columns.values() if norm(h) not in have]
            if missing:
                self.gaps[sheet or ""] = missing
                return []
        rows = [(i, [it.get(k) for k in header]) for i, it in enumerate(items, start=1)]
        return [Table(sheet, header, rows, meta)]
