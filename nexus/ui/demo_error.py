"""Demostracion de errores: altera una COPIA temporal de los datos, corre el pipeline en la copia y muestra el
balance descuadrado con su ficha de diagnostico. Nunca escribe en los archivos originales ni en la carpeta de datos.

Casos (parametros en config/demo_error.json):
  borrar    un asiento de 8,000 USD: se agrega solo uno de sus dos lados (el otro 'se borro')
  signo     un registro de 4,000 USD con el signo invertido (4,000 x 2 = 8,000 de desbalance)
  duplicar  un registro de 8,000 USD aparece dos veces (mismo dia y contraparte, sin ID: posible duplicado)
"""
import csv
import dataclasses
import io
import json
import shutil
import tempfile
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional

from ..adapters.csv_ import decode
from ..config import load_group_config
from ..currency import to_usd
from ..diagnostico import BALANCE, diagnosticar
from ..mapping import norm
from ..pipeline import run
from ..profiles import apply_profiles, load_profiles
from ..text import detect_decimal_sep, parse_period

CONFIG = Path(__file__).resolve().parent.parent.parent / "config" / "demo_error.json"
BANNER = "DEMOSTRACIÓN: datos alterados en una copia temporal"
TIPO_ESPERADO = {"borrar": "REGISTRO_IGUAL_A_D", "signo": "SIGNO_INVERTIDO", "duplicar": "DUPLICADO"}


def cargar_config(path=None) -> dict:
    return json.loads(Path(path or CONFIG).read_text(encoding="utf-8"))


def etiquetas(cfg=None) -> Dict[str, str]:
    c = cfg or cargar_config()
    m = {k: Decimal(v["monto_usd"]) for k, v in c["casos"].items()}
    return {"borrar": f"(1) Borrar un asiento de {m['borrar']:,.0f} USD",
            "signo": f"(2) Invertir el signo de un registro de {m['signo']:,.0f} USD",
            "duplicar": f"(3) Duplicar un registro de {m['duplicar']:,.0f} USD"}


@dataclass
class Demo:
    caso: str
    titulo: str
    descripcion: str
    filas: List[str]                    # lo que se agrego a la copia
    company_id: str
    period: str
    esperado: str                       # tipo de la causa candidata correcta
    diferencia_esperada: Decimal        # D = activo - (pasivo + patrimonio)
    tmp_dir: Path
    data_dir: Path
    profiles_dir: Path
    run: object = None
    ficha: object = None
    candidata_orden: Optional[int] = None
    detectada: bool = False
    extras: dict = field(default_factory=dict)


# ------------------------------------------------------------------ copia temporal
def crear_copia(data_dir, profiles_dir):
    """(tmp, datos_copia, perfiles_copia). Copia solo archivos; el original nunca se toca."""
    tmp = Path(tempfile.mkdtemp(prefix="nexus_demo_"))
    d, p = tmp / "datos", tmp / "perfiles"
    d.mkdir()
    p.mkdir()
    for src, dst in ((Path(data_dir), d), (Path(profiles_dir), p)):
        for f in src.iterdir():
            if f.is_file():
                shutil.copy2(f, dst / f.name)
    return tmp, d, p


def limpiar(tmp) -> None:
    if tmp and Path(tmp).name.startswith("nexus_demo_"):
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------ escritura en la copia (solo CSV)
def _formato(cell_sample: List[str]) -> str:
    return detect_decimal_sep(cell_sample)


def _agregar_filas_csv(path: Path, profile, periodo: str, filas: List[dict]) -> None:
    """Agrega filas al CSV de la COPIA respetando su delimitador, codificacion, formato de fecha y decimal."""
    raw = path.read_bytes()
    enc = "cp1252" if _no_utf8(raw) else "utf-8"          # se escribe con la misma codificacion que el original
    text = decode(path)
    nl = "\r\n" if "\r\n" in text else "\n"
    sample = "\n".join(text.splitlines()[:20])
    try:
        delim = csv.Sniffer().sniff(sample, delimiters=";,\t|").delimiter
    except csv.Error:
        delim = ","
    rows = list(csv.reader(io.StringIO(text), delimiter=delim))
    header = rows[0]
    pos = {c: [norm(h) for h in header].index(norm(h)) for c, h in profile.columns.items()}
    fecha = next((r[pos["period"]] for r in rows[1:] if r and parse_period(r[pos["period"]])[0] == periodo), None)
    if fecha is None:
        raise ValueError(f"El archivo {path.name} no tiene filas del periodo {periodo}")
    dec = _formato([r[pos["amount"]] for r in rows[1:] if len(r) > pos["amount"]])
    out = io.StringIO()
    w = csv.writer(out, delimiter=delim, lineterminator=nl)
    for f in filas:
        cell = [""] * len(header)
        cell[pos["period"]] = fecha
        cell[pos["account"]] = f["cuenta"]
        monto = f"{f['local']:.2f}"
        cell[pos["amount"]] = monto.replace(".", ",") if dec == "," else monto
        if "currency" in pos:
            cell[pos["currency"]] = f["moneda"]
        if "counterparty" in pos:
            cell[pos["counterparty"]] = f.get("contraparte", "")
        w.writerow(cell)
    nuevo = text if text.endswith(("\n", "\r")) else text + nl
    path.write_bytes((nuevo + out.getvalue()).encode(enc))


def _no_utf8(raw: bytes) -> bool:
    try:
        raw.decode("utf-8")
        return False
    except UnicodeDecodeError:
        return True


# ------------------------------------------------------------------ casos
def preparar(caso: str, data_dir, profiles_dir, cfg_demo=None) -> Demo:
    """Crea la copia temporal y le aplica el caso. No corre el pipeline (ver correr)."""
    c = cfg_demo or cargar_config()
    if caso not in c["casos"]:
        raise ValueError(f"Caso desconocido: {caso}")
    tmp, dd, pd_ = crear_copia(data_dir, profiles_dir)
    try:
        cfg = load_group_config(dd)
        profiles = load_profiles(pd_)
        apply_profiles(cfg, profiles)
        cid, per = c["empresa"], c["periodo"]
        prof, comp = profiles[cid], cfg.companies[cid]
        if prof.source.type != "csv":
            raise ValueError(f"La demostracion solo sabe alterar archivos CSV ({cid} es {prof.source.type})")
        fx = cfg.rates[(per, comp.currency)]
        tasa = to_usd(Decimal(1), fx)
        usd = Decimal(c["casos"][caso]["monto_usd"])
        local = usd / tasa
        if local * tasa != usd or local != local.quantize(Decimal("0.01")):
            raise ValueError(f"{usd} USD no se expresa exactamente en {comp.currency} con la tasa {fx.rate}")
        a, p_, cp = c["cuenta_activo"], c["cuenta_pasivo"], c["contraparte"]
        mon = comp.currency

        def fila(cuenta, monto, contra=""):
            return {"cuenta": cuenta, "local": monto, "moneda": mon, "contraparte": contra}
        if caso == "borrar":
            filas = [fila(p_, local)]
            desc = (f"Un asiento de {usd:,.0f} USD tiene dos lados: «{a}» (activo) y «{p_}» (pasivo). En la copia solo "
                    f"queda el lado de «{p_}»: el de «{a}» se borró.")
            dif = -usd
            titulo_filas = [f"{p_}: {local:,.2f} {mon} (= {usd:,.0f} USD)", f"{a}: (lado borrado, no está en el archivo)"]
        elif caso == "signo":
            filas = [fila(a, -local), fila(p_, local)]
            desc = (f"Un asiento de {usd:,.0f} USD: «{p_}» +{local:,.2f} {mon}, pero «{a}» quedó con el signo invertido "
                    f"(-{local:,.2f} {mon}). El desbalance es {usd:,.0f} × 2 = {2 * usd:,.0f} USD.")
            dif = -2 * usd
            titulo_filas = [f"{a}: -{local:,.2f} {mon} (signo invertido)", f"{p_}: {local:,.2f} {mon}"]
        else:
            filas = [fila(a, local, cp), fila(a, local, cp), fila(p_, local)]
            desc = (f"Un asiento de {usd:,.0f} USD: «{a}» {local:,.2f} {mon} aparece DOS veces (mismo día y contraparte, "
                    f"sin ID) y «{p_}» una vez.")
            dif = usd
            titulo_filas = [f"{a}: {local:,.2f} {mon} (aparece dos veces)", f"{p_}: {local:,.2f} {mon}"]
        _agregar_filas_csv(dd / comp.file, prof, per, filas)
        return Demo(caso, etiquetas(c)[caso], desc, titulo_filas, cid, per, TIPO_ESPERADO[caso], dif, tmp, dd, pd_,
                    extras={"archivo": comp.file, "moneda": mon, "monto_usd": usd})
    except Exception:
        limpiar(tmp)
        raise


def correr(d: Demo) -> Demo:
    """Corre el pipeline sobre la COPIA y busca la ficha de balance de la empresa y el periodo del caso."""
    d.run = run(d.data_dir, profiles_dir=d.profiles_dir)
    fichas = [f for f in diagnosticar(d.run) if f.tipo == BALANCE and f.company_id == d.company_id
              and f.period == d.period]
    d.ficha = fichas[0] if fichas else None
    if d.ficha:
        orden = next((c.orden for c in d.ficha.candidatos if c.tipo == d.esperado), None)
        d.candidata_orden, d.detectada = orden, orden is not None
    return d


def ficha_para_demo(d: Demo):
    """La misma ficha con la causa candidata correcta del caso PRIMERO. Cada candidata conserva su numero de orden
    determinista del motor (no se renumera)."""
    if d.ficha is None:
        return None
    cands = sorted(d.ficha.candidatos, key=lambda c: (c.tipo != d.esperado, c.orden))
    return dataclasses.replace(d.ficha, candidatos=cands)
