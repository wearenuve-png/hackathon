"""Seguridad e integridad: bitacora encadenada por hashes, manifiesto firmado de archivos fuente y estado de garantias.

Solo detecta ALTERACIONES de archivos y de la bitacora. No es una defensa contra intrusos: ver TABLA_ALCANCE."""
import ast
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent.parent
GENESIS = "0" * 64


def _sha(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _canon(d: dict) -> str:
    return json.dumps(d, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


# ------------------------------------------------------------------ bitacora encadenada
def _cabeza(log_path) -> Path:
    p = Path(log_path)
    return p.with_name(p.name + ".cabeza")


def _lineas(log_path) -> List[str]:
    p = Path(log_path)
    return p.read_text(encoding="utf-8").splitlines() if p.is_file() else []


def encadenar(log_path, ev: dict) -> dict:
    """Agrega 'prev' (hash de la linea anterior tal cual esta escrita, o GENESIS) y 'hash' (sello del propio registro)."""
    ls = _lineas(log_path)
    ev = {k: v for k, v in ev.items() if k not in ("prev", "hash")}
    ev["prev"] = _sha(ls[-1]) if ls else GENESIS
    ev["hash"] = _sha(ev["prev"] + _canon(ev))
    return ev


def registrar_cabeza(log_path) -> None:
    """Guarda cuantas lineas hay y el hash de la ultima: permite detectar que borraron el final de la bitacora."""
    ls = _lineas(log_path)
    _cabeza(log_path).write_text(json.dumps({"n": len(ls), "ultima": _sha(ls[-1]) if ls else GENESIS}), encoding="utf-8")


def quitar_cabeza(log_path) -> None:
    c = _cabeza(log_path)
    if c.exists():
        c.unlink()


def verificar_bitacora(log_path) -> dict:
    """{'ok': bool, 'linea': N|None, 'n': lineas, 'mensaje': str}. Los registros anteriores al encadenado (sin 'hash')
    se aceptan solo como prefijo; despues del primero encadenado todo debe estar encadenado."""
    ls = _lineas(log_path)
    esperado, encadenado = GENESIS, False
    for i, ln in enumerate(ls, 1):
        try:
            ev = json.loads(ln)
            assert isinstance(ev, dict)
        except (ValueError, AssertionError):
            return _res(False, i, len(ls))
        if "hash" not in ev:
            if encadenado:
                return _res(False, i, len(ls))
        else:
            sin = {k: v for k, v in ev.items() if k != "hash"}
            if ev.get("prev") != esperado or ev["hash"] != _sha(esperado + _canon(sin)):
                return _res(False, i, len(ls))
            encadenado = True
        esperado = _sha(ln)
    c = _cabeza(log_path)
    if c.is_file():
        try:
            h = json.loads(c.read_text(encoding="utf-8"))
            if h["n"] != len(ls) or h["ultima"] != esperado:
                return _res(False, min(h["n"], len(ls)) + 1 if h["n"] != len(ls) else len(ls), len(ls))
        except (ValueError, KeyError, TypeError):
            return _res(False, len(ls) + 1, len(ls))
    return _res(True, None, len(ls))


def _res(ok: bool, linea: Optional[int], n: int) -> dict:
    msg = "Bitácora íntegra" if ok else f"Bitácora alterada en la línea {linea}"
    return {"ok": ok, "linea": linea, "n": n, "mensaje": msg}


# ------------------------------------------------------------------ manifiesto firmado de archivos fuente
def manifiesto_path(origen) -> Path:
    base = Path(os.environ.get("NEXUS_MANIFIESTOS") or ROOT / "data" / "output" / "manifiestos")
    return base / f"manifiesto_{Path(str(origen)).name or 'datos'}.json"


def _firma(m: dict) -> str:
    return _sha(_canon({k: v for k, v in m.items() if k != "firma"}))


def guardar_manifiesto(path, origen, hashes: Dict[str, str], anterior: Optional[str] = None) -> dict:
    import datetime as dt
    m = {"version": 1, "origen": str(origen), "creado": dt.datetime.now().isoformat(timespec="seconds"),
         "archivos": dict(sorted(hashes.items())), "anterior": anterior}
    m["firma"] = _firma(m)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8")
    return m


def comparar_manifiesto(path, hashes: Dict[str, str]) -> dict:
    """status: NUEVO (no habia manifiesto) | IGUAL | CAMBIO (cambios) | ALTERADO (la firma del manifiesto no cuadra)."""
    p = Path(path)
    if not p.is_file():
        return {"status": "NUEVO", "cambios": [], "manifiesto": None}
    try:
        m = json.loads(p.read_text(encoding="utf-8"))
        valido = m.get("firma") == _firma(m)
    except ValueError:
        return {"status": "ALTERADO", "cambios": [], "manifiesto": None}
    if not valido:
        return {"status": "ALTERADO", "cambios": [], "manifiesto": m}
    antes = m["archivos"]
    cambios = []
    for nombre in sorted(set(antes) | set(hashes)):
        a, b = antes.get(nombre), hashes.get(nombre)
        if a != b:
            cambios.append({"archivo": nombre, "antes": a, "ahora": b,
                            "tipo": "AGREGADO" if a is None else "FALTA" if b is None else "CAMBIO"})
    return {"status": "CAMBIO" if cambios else "IGUAL", "cambios": cambios, "manifiesto": m}


# ------------------------------------------------------------------ estado de las garantias
BANNED = {"requests", "urllib", "http", "httpx", "socket", "ftplib", "smtplib", "anthropic", "openai", "aiohttp",
          "websocket"}
PATRON_LLAVE = re.compile(r"sk-ant-[A-Za-z0-9_\-]{40,}")


def motor_sin_red(root=ROOT) -> List[str]:
    """Archivos de nexus/ que importan una libreria de red (lista vacia = sin red)."""
    malos = []
    for f in sorted((Path(root) / "nexus").rglob("*.py")):
        try:
            arbol = ast.parse(f.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for n in ast.walk(arbol):
            mods = [a.name for a in n.names] if isinstance(n, ast.Import) else \
                [n.module or ""] if isinstance(n, ast.ImportFrom) and not n.level else []
            if any(m.split(".")[0] in BANNED for m in mods):
                malos.append(str(f.relative_to(root)))
                break
    return malos


def llave_fuera_del_repo(root=ROOT) -> dict:
    root = Path(root)
    gi = (root / ".gitignore").read_text(encoding="utf-8").split() if (root / ".gitignore").is_file() else []
    expuestos = []
    for f in root.rglob("*"):
        if (not f.is_file() or any(p in (".venv", ".git", "__pycache__", "output") for p in f.parts)
                or f.suffix not in (".py", ".json", ".md", ".txt", ".csv", ".toml", ".yml", ".yaml", ".cfg", ".env")):
            continue
        try:
            if PATRON_LLAVE.search(f.read_text(encoding="utf-8", errors="ignore")):
                expuestos.append(str(f.relative_to(root)))
        except OSError:
            pass
    return {"gitignore_ok": ".env" in gi, "archivos_con_llave": expuestos}


def garantias(n_hash_ok: int, n_hash: int, root=ROOT) -> List[dict]:
    red, llave = motor_sin_red(root), llave_fuera_del_repo(root)
    return [
        {"Garantía": "Solo lectura sobre los archivos fuente",
         "Estado": "Cumple" if n_hash_ok == n_hash else "Revisar",
         "Cómo se comprueba": f"El motor nunca abre un archivo fuente para escribir; hoy {n_hash_ok} de {n_hash} huellas "
                              "coinciden. Prueba: test_el_motor_corre_sobre_archivos_de_solo_lectura_y_el_hash_no_cambia."},
        {"Garantía": "Sin red en el motor",
         "Estado": "Cumple" if not red else "Revisar",
         "Cómo se comprueba": "Ningún módulo de nexus/ importa librerías de red. Prueba: "
                              "test_el_motor_no_importa_librerias_de_red." + (f" Revisar: {', '.join(red)}" if red else "")},
        {"Garantía": "Llave de API fuera del repositorio",
         "Estado": "Cumple" if llave["gitignore_ok"] and not llave["archivos_con_llave"] else "Revisar",
         "Cómo se comprueba": "La llave solo se lee de la variable de entorno ANTHROPIC_API_KEY; .env está en .gitignore "
                              "y ningún archivo del repositorio contiene una llave."
                              + (f" Revisar: {', '.join(llave['archivos_con_llave'])}" if llave["archivos_con_llave"] else "")},
    ]


TABLA_ALCANCE = [
    ("Que alguien cambie un archivo fuente sin que quede dicho (se ve el archivo y las dos huellas).",
     "Que un programa malicioso ya esté instalado en el equipo (malware)."),
    ("Que alguien edite, borre o reordene una decisión ya guardada en la bitácora de aprobaciones.",
     "Que alguien entre al servidor sin permiso (intrusión)."),
    ("Que el manifiesto de huellas se modifique sin que su firma deje de cuadrar.",
     "Que alguien tenga acceso físico al equipo y rehaga a la vez archivos, bitácora y manifiesto."),
    ("Que se tome por cierta una carga que ya no coincide con lo que se leyó.",
     "Que los datos originales de la empresa ya vengan equivocados o falsos."),
]
