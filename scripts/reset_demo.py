"""Restablece la demostracion: deja VACIO el registro de aprobaciones (data/output/aprobaciones.jsonl o la ruta de la
variable NEXUS_APROBACIONES). No toca ningun archivo fuente: lo comprueba con hashes antes y despues.

    .venv/bin/python scripts/reset_demo.py [--registro RUTA]

En la app, el selector vuelve a «Datos base» al abrirla de nuevo (o con el boton «Restablecer»)."""
import argparse
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from nexus.ui import correcciones  # noqa: E402


def huellas():
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
            for d in ("data/synthetic", "data/demo_errores", "profiles") for p in sorted((ROOT / d).rglob("*"))
            if p.is_file()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--registro", default=None, help="ruta del registro (por defecto, el de la app)")
    a = ap.parse_args()
    ruta = Path(a.registro) if a.registro else correcciones.log_por_defecto()
    antes = huellas()
    n = correcciones.restablecer(ruta)
    if huellas() != antes:
        print("ERROR: algun archivo fuente cambio (no deberia pasar)")
        sys.exit(1)
    print(f"Demostracion restablecida: {n} evento(s) quitado(s) de {ruta}. Archivos fuente sin tocar "
          f"({len(antes)} verificados).")


if __name__ == "__main__":
    main()
