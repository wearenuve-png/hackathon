"""Carga automatica de presupuestos desde una o varias carpetas elegidas por la persona.

FinaCore lee los archivos en SOLO LECTURA. Si hay una sola carpeta completa se usa tal cual; si hay varias, se arma una
carpeta de trabajo con COPIAS (los originales no se tocan). No se adivina nada: si falta la configuracion del grupo
(empresas, tasas, catalogo, equivalencias, periodos) o un archivo de empresa, se dice exactamente que falta."""
import csv
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

from ..config import load_group_config

ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG = ("empresas.csv", "tasas.csv", "catalogo_cuentas.csv", "equivalencias.csv", "periodos.csv")
EXT = (".xlsx", ".csv", ".json")
MARCA = ".nexus_carga"


def carpeta_trabajo() -> Path:
    return Path(os.environ.get("NEXUS_CARGA") or ROOT / "data" / "output" / "carga_auto")


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def modo_publico() -> bool:
    """FINACORE_PUBLICO=1: la app esta expuesta a internet. Solo se aceptan carpetas del proyecto (data/...) o archivos
    subidos; no se puede apuntar a carpetas arbitrarias de la maquina que sirve la app."""
    return os.environ.get("FINACORE_PUBLICO", "") not in ("", "0")


def preparar(carpetas: List[str], base: Optional[Path] = None) -> dict:
    """{'ok', 'dir', 'origen', 'copiado', 'usados', 'sin_usar', 'problemas'}. Nunca lanza una excepcion tecnica."""
    out = {"ok": False, "dir": None, "origen": [], "copiado": False, "usados": [], "sin_usar": [], "problemas": [],
           "perfiles": None}
    rutas = []
    for c in carpetas:
        c = (c or "").strip().strip('"').strip("'")
        if not c:
            continue
        p = Path(c).expanduser()
        if not p.is_absolute():
            p = ROOT / p                              # rutas relativas (data/demo) se leen desde la raiz del proyecto
        if modo_publico() and not _dentro(p, ROOT / "data") and not _dentro(p, carpeta_trabajo()):
            out["problemas"].append("En el modo público solo se pueden usar las carpetas del proyecto (por ejemplo "
                                    "data/demo) o subir los archivos desde tu computadora.")
        elif not p.is_dir():
            out["problemas"].append(f"La carpeta no existe o no se puede abrir: {c}")
        elif p.resolve() not in rutas:
            rutas.append(p.resolve())
    if not rutas and not out["problemas"]:
        out["problemas"].append("Escribe o elige al menos una carpeta.")
    if out["problemas"]:
        return out
    out["origen"] = [str(r) for r in rutas]
    archivos: Dict[str, Path] = {}
    for r in rutas:
        try:
            for f in sorted(r.iterdir()):
                if not f.is_file() or f.name.startswith((".", "~$")) or not (f.suffix.lower() in EXT):
                    continue
                if f.name in archivos and _sha(archivos[f.name]) != _sha(f):
                    out["problemas"].append(f"El archivo «{f.name}» está en dos carpetas con contenido distinto; "
                                            "deja solo la versión correcta.")
                archivos.setdefault(f.name, f)
        except OSError:
            out["problemas"].append(f"No se pudo leer la carpeta {r}.")
    falta = [c for c in CONFIG if c not in archivos]
    if falta:
        out["problemas"].append("Falta la configuración del grupo: " + ", ".join(falta) + ". FinaCore no adivina qué "
                                "empresa, moneda o tasa corresponde a cada archivo; agrégalos en alguna de las carpetas.")
    if out["problemas"]:
        return out
    try:
        with open(archivos["empresas.csv"], encoding="utf-8-sig", newline="") as f:
            esperados = [r["archivo"] for r in csv.DictReader(f)]
    except (OSError, KeyError, UnicodeDecodeError, csv.Error):
        out["problemas"].append("No se pudo leer empresas.csv (columnas esperadas: company_id, nombre, pais, "
                                "moneda_funcional, archivo, alias).")
        return out
    ausentes = [a for a in esperados if a not in archivos]
    if ausentes:
        out["problemas"].append("empresas.csv pide estos presupuestos y no están en las carpetas: " + ", ".join(ausentes))
        return out
    out["usados"] = list(esperados)
    out["sin_usar"] = sorted(n for n in archivos if n not in esperados and n not in CONFIG)
    if len(rutas) == 1 and all(archivos[n].parent == rutas[0] for n in list(CONFIG) + esperados):
        destino = rutas[0]
    else:
        clave = hashlib.sha256("".join(f"{n}:{_sha(archivos[n])}" for n in sorted(list(CONFIG) + esperados))
                               .encode()).hexdigest()[:12]
        destino = (base or carpeta_trabajo()) / clave
        try:
            destino.mkdir(parents=True, exist_ok=True)
            (destino / MARCA).write_text("copias de trabajo creadas por FinaCore; se pueden borrar\n", encoding="utf-8")
            for n in list(CONFIG) + esperados:
                shutil.copy2(archivos[n], destino / n)
        except OSError:
            out["problemas"].append("No se pudo preparar la carpeta de trabajo.")
            return out
        out["copiado"] = True
    for r in rutas:                      # perfiles de lectura aprobados: una subcarpeta «perfiles» con archivos .json
        if (r / "perfiles").is_dir() and any((r / "perfiles").glob("*.json")):
            out["perfiles"] = str(r / "perfiles")
            break
    try:
        load_group_config(destino)
    except Exception as e:  # noqa: BLE001 - se explica sin mostrar el error tecnico
        out["problemas"].append("La configuración del grupo tiene un problema de formato"
                                f" ({type(e).__name__}); revisa empresas, tasas, catálogo, equivalencias y períodos.")
        return out
    out.update(ok=True, dir=str(destino))
    return out


MAX_SUBIDA_MB = 60


def _dentro(p: Path, raiz: Path) -> bool:
    try:
        p.resolve().relative_to(raiz.resolve())
        return True
    except ValueError:
        return False


def guardar_subidas(archivos, base: Optional[Path] = None) -> Optional[Path]:
    """Guarda en una carpeta de trabajo los archivos que la persona subio desde el navegador (lista de (nombre, bytes)).
    Sirve cuando la app corre en un servidor y la persona no tiene una carpeta en esa maquina. Devuelve la carpeta,
    o None si no hay archivos validos o pesan mas del limite."""
    validos = [(Path(n).name, b) for n, b in archivos
               if Path(n).name and not Path(n).name.startswith(".") and Path(n).suffix.lower() in EXT]
    if not validos or sum(len(b) for _, b in validos) > MAX_SUBIDA_MB * 1024 * 1024:
        return None
    clave = hashlib.sha256("".join(f"{n}:{hashlib.sha256(b).hexdigest()}" for n, b in sorted(validos)).encode()).hexdigest()[:12]
    destino = (base or carpeta_trabajo()) / f"subidas-{clave}"
    try:
        destino.mkdir(parents=True, exist_ok=True)
        (destino / MARCA).write_text("archivos subidos desde el navegador; se pueden borrar\n", encoding="utf-8")
        for n, b in validos:
            (destino / n).write_bytes(b)
    except OSError:
        return None
    return destino


def elegir_carpeta() -> Optional[str]:
    """Selector de carpeta del sistema (macOS). None si se cancela o no esta disponible: se puede escribir la ruta."""
    if sys.platform != "darwin" or modo_publico():
        return None
    try:
        r = subprocess.run(["osascript", "-e", 'POSIX path of (choose folder with prompt "Carpeta con los presupuestos")'],
                           capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.SubprocessError):
        return None
    ruta = r.stdout.strip()
    return ruta if r.returncode == 0 and ruta else None
