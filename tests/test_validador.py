from validador.datos_demo import generar, CATALOGO, LIMPIAS
from validador.motor import validar, puerta


def _correr():
    df, ref = generar()
    return df, validar(df, ref)


def test_encuentra_todos_los_errores_sembrados():
    _, (hallazgos, _) = _correr()
    encontrados = {(h.empresa, h.regla) for h in hallazgos}
    faltan = [c for c in CATALOGO if c not in encontrados]
    assert not faltan, f"No se detectaron: {faltan}"


def test_sin_falsos_positivos_en_empresa_limpia():
    _, (hallazgos, semaforo) = _correr()
    for e in LIMPIAS:
        assert semaforo[e]["estado"] == "VERDE", [h.regla for h in hallazgos if h.empresa == e]


def test_diagnostico_de_moneda():
    _, (hallazgos, _) = _correr()
    h = next(x for x in hallazgos if x.regla == "moneda.equivocada")
    assert h.empresa == "D" and "GTQ" in h.mensaje


def test_intercompania_marca_diferencia_29000_vs_30000():
    _, (hallazgos, _) = _correr()
    h = next(x for x in hallazgos if x.regla == "intercompania.diferencia")
    assert "30,000.00" in h.mensaje and "29,000.00" in h.mensaje


def test_tasa_fuera_de_rango_bloquea_todo():
    df, ref = generar()
    _, semaforo = validar(df, ref, tasas={"USD": 1.0, "GTQ": 80.0, "MXN": 20.0})
    assert all(s["estado"] == "ROJO" for s in semaforo.values())


def test_sin_historial_no_se_da_por_bueno():
    """Si no hay referencia para verificar la moneda, la empresa limpia NO queda en verde."""
    df, _ = generar()
    _, semaforo = validar(df, None)
    assert semaforo["B"]["estado"] == "SIN_VERIFICAR" and "moneda" in semaforo["B"]["sin_verificar"]
    _, ok = puerta(df, semaforo)
    assert "B" not in ok


def test_lo_bloqueado_no_pasa_a_consolidacion():
    df, (_, semaforo) = _correr()
    pasan, ok = puerta(df, semaforo)
    assert "B" in ok
    assert not {"C", "D", "E", "F"} & set(ok)
    assert set(pasan["empresa"]) == set(ok)
