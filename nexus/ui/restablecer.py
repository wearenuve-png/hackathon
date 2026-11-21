"""Boton 'Restablecer': borra TODO lo que el programa guarda por su cuenta. Nunca toca archivos fuente."""
import shutil
from pathlib import Path

from . import carga_auto, correcciones


def limpiar_todo(log_path, manifiestos_dir, carga_dir=None) -> dict:
    """Vacia la bitacora de aprobaciones (y su ancla), borra los manifiestos de huellas y las copias de trabajo de
    cargas desde carpetas. Los presupuestos originales, los datos de ejemplo y las evidencias exportadas no se tocan."""
    eventos = correcciones.restablecer(log_path)
    manifiestos = 0
    md = Path(manifiestos_dir)
    if md.is_dir():
        for f in md.glob("manifiesto_*.json"):
            f.unlink()
            manifiestos += 1
    copias = 0
    cd = Path(carga_dir) if carga_dir else carga_auto.carpeta_trabajo()
    if cd.is_dir():
        for sub in cd.iterdir():
            if sub.is_dir() and (sub / carga_auto.MARCA).is_file():      # solo carpetas creadas por NEXUS
                shutil.rmtree(sub)
                copias += 1
    return {"eventos": eventos, "manifiestos": manifiestos, "copias": copias}
