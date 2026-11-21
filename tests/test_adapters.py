import pytest

from conftest import DATA
from nexus.adapters import ADAPTERS, SourceAdapter
from nexus.pipeline import run


def test_hay_un_adaptador_por_formato_con_clase_base_comun():
    assert set(ADAPTERS) == {"xlsx", "csv", "json"}
    for cls in ADAPTERS.values():
        assert issubclass(cls, SourceAdapter) and cls.extract is not SourceAdapter.extract


def test_la_clase_base_no_se_instancia():
    with pytest.raises(TypeError):
        SourceAdapter()


def test_con_perfiles_el_resultado_es_identico_al_modo_legado(built_profiles, key):
    a = run(DATA, ic_tolerance_usd=key["tolerancia_intercompania_usd"])
    b = run(DATA, ic_tolerance_usd=key["tolerancia_intercompania_usd"], profiles_dir=built_profiles)
    assert {r.record_id: (r.status, r.amount_original, r.amount_usd, r.account_code) for r in a.records} == \
           {r.record_id: (r.status, r.amount_original, r.amount_usd, r.account_code) for r in b.records}
    for p in key["consolidado_esperado_usd"]:
        assert a.periods[p].summary == b.periods[p].summary
    assert all(r.status == "MATCHED" for r in b.load_reports.values())
    assert all(r.status == "AUTO" for r in a.load_reports.values())


def test_reporte_de_carga_guarda_version_y_aprobacion(built_profiles, key):
    b = run(DATA, profiles_dir=built_profiles)
    for rep in b.load_reports.values():
        assert rep.profile_version == 1 and rep.approval_status == "APPROVED" and rep.n_records > 0


def test_fuente_que_cambia_de_formato_queda_en_revision(built_profiles, data_copy):
    f = data_copy / "distribuidora_central_gt.csv"
    txt = f.read_text(encoding="utf-8").replace("importe;", "monto_total;", 1)   # cambia un encabezado
    f.write_text(txt, encoding="utf-8")
    res = run(data_copy, profiles_dir=built_profiles)
    rep = res.load_reports["EMP002"]
    assert rep.status == "REVIEW" and any("importe" in r for r in rep.reasons)
    assert not [r for r in res.records if r.company_id == "EMP002"]          # nada se procesa en silencio
    assert any(f.rule_id == "CARGA-01" and f.company_id == "EMP002" for f in res.findings)
    assert all(res.periods[p].provisional and "EMP002" in res.periods[p].missing_companies for p in res.periods)
    assert res.load_reports["EMP001"].status == "MATCHED"                   # las demas siguen


def test_hoja_faltante_en_excel_queda_en_revision(built_profiles, data_copy):
    from openpyxl import load_workbook
    f = data_copy / "ferrex_el_salvador.xlsx"
    wb = load_workbook(f)
    del wb["Balance Sheet"]
    wb.save(f)
    rep = run(data_copy, profiles_dir=built_profiles).load_reports["EMP004"]
    assert rep.status == "REVIEW" and any("Balance Sheet" in r for r in rep.reasons)


def test_archivo_con_otro_tipo_que_el_perfil_queda_en_revision(built_profiles, data_copy):
    (data_copy / "transportes_ferrex_hn.csv").rename(data_copy / "transportes_ferrex_hn.json")
    import json
    p = built_profiles / "EMP005.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    d["source"]["file"] = "transportes_ferrex_hn.json"
    d.pop("profile_hash")
    p.write_text(json.dumps(d), encoding="utf-8")
    rep = run(data_copy, profiles_dir=built_profiles).load_reports["EMP005"]
    assert rep.status == "REVIEW"


def test_columna_nueva_no_declarada_se_avisa_pero_no_rompe(built_profiles, data_copy):
    import csv, io
    f = data_copy / "distribuidora_central_gt.csv"
    rows = list(csv.reader(io.StringIO(f.read_text(encoding="utf-8")), delimiter=";"))
    rows[0].append("comentario")
    for r in rows[1:]:
        r.append("")
    out = io.StringIO()
    csv.writer(out, delimiter=";", lineterminator="\n").writerows(rows)
    f.write_text(out.getvalue(), encoding="utf-8")
    rep = run(data_copy, profiles_dir=built_profiles).load_reports["EMP002"]
    assert rep.status == "MATCHED" and any("comentario" in n for n in rep.notes)
