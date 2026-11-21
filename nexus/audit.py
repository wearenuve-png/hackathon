"""Registro de ejecuciones: hashes de entrada, version de reglas y salidas reproducibles."""
import csv
import hashlib
import json
from decimal import Decimal
from pathlib import Path


def file_hashes(paths) -> dict:
    return {Path(p).name: sha256_file(p) for p in paths}


def sha256_file(path) -> str:
    """Lectura en bloques, solo lectura: nunca abre el archivo en modo escritura."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_hashes(hashes: dict, dirs) -> dict:
    """Vuelve a calcular el SHA-256 de cada archivo registrado: OK (igual), CAMBIO (distinto) o FALTA."""
    out = {}
    for name, registered in hashes.items():
        path = next((Path(d) / name for d in dirs if (Path(d) / name).is_file()), None)
        if path is None:
            out[name] = {"status": "FALTA", "registered": registered, "current": None}
            continue
        cur = sha256_file(path)
        out[name] = {"status": "OK" if cur == registered else "CAMBIO", "registered": registered, "current": cur,
                     "path": str(path)}
    return out


def _default(o):
    if isinstance(o, Decimal):
        return str(o)
    if hasattr(o, "isoformat"):
        return o.isoformat()
    if hasattr(o, "__dict__"):
        return o.__dict__
    return str(o)


def write_run(run, output_dir, source_dir=None) -> str:
    """source_dir (opcional): carpeta del servidor de donde se leyeron los archivos; queda en la evidencia."""
    d = Path(output_dir) / run.run_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "run.json").write_text(json.dumps({
        "run_id": run.run_id, "rules_version": run.config.rules_version,
        "source": {"kind": "server_folder", "mode": "read_only", "path": str(source_dir) if source_dir else None,
                   "network": "none"},
        "ic_tolerance_usd": run.config.ic_tolerance_usd, "input_hashes": run.input_hashes,
        "periods": {p: {"kind": pr.kind, "provisional": pr.provisional, "provisional_reasons": pr.provisional_reasons,
                        "summary": pr.summary, "naive_summary": pr.naive_summary,
                        "lines": {c: {"amount_usd": ln.amount_usd, "gross_usd": ln.gross_usd}
                                  for c, ln in pr.lines.items()},
                        "excluded": pr.excluded, "excluded_usd_by_status": pr.excluded_usd_by_status,
                        "missing_companies": pr.missing_companies}
                    for p, pr in run.periods.items()},
        "load_reports": run.load_reports, "matches": run.matches, "adjustments": run.adjustments, "findings": run.findings,
    }, default=_default, indent=2, ensure_ascii=False), encoding="utf-8")
    with open(d / "records.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        cols = ["record_id", "company_id", "source_file", "source_sheet", "source_row", "period", "account_local",
                "account_code", "amount_original", "currency", "fx_rate", "fx_orientation", "amount_usd", "status",
                "status_reasons", "flags", "counterparty_id", "transaction_id", "ic_match_id", "adjustment_ids"]
        w.writerow(cols)
        for r in run.records:
            w.writerow([getattr(r, c) if not isinstance(getattr(r, c), list) else "; ".join(getattr(r, c))
                        for c in cols])
    return str(d)


# ------------------------------------------------------------------ paquete de auditoria (zip)
def _q2(d):
    from decimal import ROUND_HALF_UP
    return "" if d is None else str(Decimal(d).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def build_audit_package(run, source_dir=None) -> bytes:
    """Zip en memoria con todo lo necesario para auditar una ejecucion: consolidado y resumen por periodo, ajustes,
    alertas, discrepancias, perfiles, hashes SHA-256, run.json y records.csv. No escribe en la carpeta fuente."""
    import dataclasses
    import io
    import tempfile
    import zipfile

    def csv_bytes(header, rows):
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)
        return buf.getvalue().encode("utf-8")

    cfg = run.config
    files = {}
    files["consolidado.csv"] = csv_bytes(
        ["periodo", "estado_periodo", "cuenta", "nombre", "antes_de_eliminar_usd", "consolidado_usd"],
        [[p, "PROVISIONAL" if pr.provisional else "DEFINITIVO", c, cfg.catalog[c].name, _q2(ln.gross_usd),
          _q2(ln.amount_usd)] for p, pr in sorted(run.periods.items()) for c, ln in pr.lines.items()])
    keys = ["ingresos", "costo_ventas", "gastos_operativos", "ebit", "gastos_financieros", "impuestos",
            "utilidad_neta", "activo_total", "pasivo_total", "patrimonio"]
    files["resumen.csv"] = csv_bytes(
        ["periodo", "estado_periodo", "concepto", "suma_ingenua_usd", "consolidado_usd"],
        [[p, "PROVISIONAL" if pr.provisional else "DEFINITIVO", k, _q2(pr.naive_summary[k]), _q2(pr.summary[k])]
         for p, pr in sorted(run.periods.items()) for k in keys])
    files["ajustes.csv"] = csv_bytes(
        ["ajuste", "tipo", "periodo", "cuenta", "usd", "registros", "regla", "motivo", "reversible", "aprobado_por"],
        [[a.adjustment_id, a.kind, a.period, a.account_code, _q2(a.amount_usd), "; ".join(a.record_ids), a.rule,
          a.reason, a.reversible, a.approved_by] for a in run.adjustments])
    files["alertas.csv"] = csv_bytes(
        ["severidad", "regla", "empresa", "periodo", "mensaje", "encontrado", "esperado", "sugerencia", "impacto"],
        [[f.severity, f.rule_id, f.company_id, f.period, f.message, f.found, f.expected, f.suggestion, f.impact]
         for f in run.findings])
    files["discrepancias.csv"] = csv_bytes(
        ["periodo", "estado", "vendedor", "comprador", "referencia", "tipo", "usd_vendedor", "usd_comprador",
         "diferencia_usd"],
        [[m.period, m.status, m.seller_id, m.buyer_id, m.reference, "operacion" if m.statement == "ER" else "saldo",
          _q2(m.seller_usd), _q2(m.buyer_usd), _q2(m.difference_usd)]
         for m in run.matches if m.status != "RECONCILED"])
    files["hashes_sha256.csv"] = csv_bytes(["archivo", "sha256"], sorted(run.input_hashes.items()))
    for cid, p in cfg.profiles.items():
        files[f"perfiles/{cid}.json"] = json.dumps(dataclasses.asdict(p), indent=2, ensure_ascii=False).encode("utf-8")
    files["LEEME.txt"] = (
        f"Paquete de auditoria FinaCore\nEjecucion: {run.run_id}\nReglas: {run.config.rules_version}\n"
        f"Fuente: carpeta del servidor, solo lectura: {source_dir}\nSin conexion a internet.\n"
        "DATOS SINTETICOS si se trata del grupo de demostracion.\n\n"
        "consolidado.csv / resumen.csv: cifras en USD por periodo (con su estado PROVISIONAL o DEFINITIVO)\n"
        "ajustes.csv: eliminaciones intercompania y duplicados excluidos (reversibles)\n"
        "alertas.csv: hallazgos del validador; discrepancias.csv: lo que NO se elimino\n"
        "perfiles/: perfiles de integracion (version y quien los aprobo)\n"
        "hashes_sha256.csv: huella de cada archivo leido\nrun.json y records.csv: evidencia completa por registro\n"
    ).encode("utf-8")
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(write_run(run, tmp, source_dir))
        files["run.json"] = (d / "run.json").read_bytes()
        files["records.csv"] = (d / "records.csv").read_bytes()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data)
    return buf.getvalue()
