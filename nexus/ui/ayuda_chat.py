"""Chat de la Ayuda: responde SOLO con el texto que ya esta en la pestana Ayuda (glosario, preguntas frecuentes y
limitaciones). Busqueda por palabras, local y determinista: no hay modelo de lenguaje, ni red, ni cifras nuevas."""
import re
import unicodedata
from typing import List, Optional, Tuple

from ..limitaciones import LIMITACIONES

NO_ENCONTRADO = ("No encontré eso en la Ayuda. Prueba con una palabra clave (por ejemplo: provisional, duplicado, "
                 "tasa, intercompañía, bloqueado, simulación) o usa las preguntas frecuentes de arriba.")
STOP = set("que qué es son de del la las el los un una unos unas en y o a por para con sin se me mi tu su al lo "
           "como cómo cual cuál cuales donde dónde cuando cuándo porque porqué hay esta este esto eso nexus puede "
           "pueden significa quiere decir".split())


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _tokens(s: str) -> set:
    # prefijo de 5 letras: "duplicados" ~ "duplicado", "bloquea" ~ "bloqueado"
    return {w[:5] for w in re.findall(r"[a-z0-9]+", _norm(s)) if w not in {_norm(x) for x in STOP} and len(w) > 2}


def entradas() -> List[Tuple[str, str, str]]:
    """(seccion, titulo, texto) de todo lo que hay en la Ayuda."""
    from .tab_ayuda import FAQ, GLOSARIO
    out = [("Glosario", t, d) for t, d in GLOSARIO] + [("Preguntas frecuentes", q, a) for q, a in FAQ]
    out += [("Qué NO puede detectar NEXUS", f"{i}. {t}", d) for i, t, d in LIMITACIONES]
    return out


def buscar(pregunta: str) -> dict:
    """{'respuesta', 'fuente', 'tambien': [titulos], 'encontrada': bool}."""
    q = _tokens(pregunta)
    puntajes = []
    for sec, titulo, texto in entradas():
        t, b = _tokens(titulo), _tokens(texto)
        p = 3 * len(q & t) + len(q & b)
        if p:
            puntajes.append((p, sec, titulo, texto))
    puntajes.sort(key=lambda x: -x[0])
    if not q or not puntajes or puntajes[0][0] < 2:
        return {"respuesta": NO_ENCONTRADO, "fuente": None, "tambien": [], "encontrada": False}
    _, sec, titulo, texto = puntajes[0]
    return {"respuesta": texto, "fuente": f"Ayuda → {sec} → {titulo}", "encontrada": True,
            "tambien": [t for _, _, t, _ in puntajes[1:3]]}
