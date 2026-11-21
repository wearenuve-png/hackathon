import json
from pathlib import Path

CONFIG = Path(__file__).resolve().parent.parent / "config" / "asistente.json"
DEFAULTS = {"modelo": "claude-haiku-5-5", "max_tokens": 900, "timeout_s": 30, "max_mensajes_historial": 20}


def cargar_config(path=None) -> dict:
    """Configuracion con valores por defecto; un archivo ausente o invalido nunca rompe nada."""
    cfg = dict(DEFAULTS)
    try:
        d = json.loads(Path(path or CONFIG).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return cfg
    if isinstance(d.get("modelo"), str) and d["modelo"].strip():
        cfg["modelo"] = d["modelo"].strip()
    for k in ("max_tokens", "timeout_s", "max_mensajes_historial"):
        v = d.get(k)
        if isinstance(v, int) and not isinstance(v, bool) and v > 0:
            cfg[k] = v
    return cfg
