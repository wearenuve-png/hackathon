"""Asistente NEXUS (prototipo): modo local sin llave, cliente simulado, llave nunca expuesta, contexto sin filas crudas."""
import json
from decimal import Decimal
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from asistente import cliente, local
from asistente.contexto import construir_contexto
from nexus.pipeline import run

ROOT = Path(__file__).resolve().parent.parent
KEY = json.loads((ROOT / "tests/fixtures/answer_key.json").read_text(encoding="utf-8"))
LLAVE = "sk-ant-LLAVE-SECRETA-DE-PRUEBA-123"


class Mock:
    def __init__(self, texto="Respuesta de prueba (Estados financieros).", falla=False):
        self.texto, self.falla, self.llamadas = texto, falla, []

    def responder(self, system, mensajes):
        self.llamadas.append((system, mensajes))
        if self.falla:
            raise RuntimeError(f"fallo de red con {LLAVE}")
        return self.texto


@pytest.fixture(scope="module")
def res():
    return run(ROOT / "data/synthetic", profiles_dir=ROOT / "profiles")


@pytest.fixture
def ctx(res):
    return construir_contexto(res, "2026-10", "Datos base")


@pytest.fixture(autouse=True)
def _limpia_mock(monkeypatch):
    monkeypatch.setattr(cliente, "_CLIENTE_INYECTADO", None)


def test_sin_llave_no_hay_cliente_y_cae_a_modo_local():
    assert cliente.obtener_cliente() is None


def test_con_llave_e_inyeccion_hay_cliente(monkeypatch):
    m = Mock()
    monkeypatch.setenv("ANTHROPIC_API_KEY", LLAVE)
    monkeypatch.setattr(cliente, "_CLIENTE_INYECTADO", m)
    assert cliente.obtener_cliente() is m


def test_sin_sdk_instalado_cae_a_modo_local(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", LLAVE)
    import sys
    monkeypatch.setitem(sys.modules, "anthropic", None)       # import falla
    assert cliente.obtener_cliente() is None


def test_la_llave_no_aparece_en_ninguna_salida(monkeypatch, ctx):
    monkeypatch.setenv("ANTHROPIC_API_KEY", LLAVE)
    m = Mock(texto=f"hola {LLAVE}")
    out = cliente.preguntar(m, ctx, [], "¿qué pasó?")
    assert LLAVE not in out and "[llave oculta]" in out
    assert LLAVE not in repr(cliente.ClienteAnthropic.__repr__) and LLAVE not in json.dumps(ctx, default=str)
    assert LLAVE not in cliente.sistema_con_contexto(ctx)
    for k, _ in local.PREGUNTAS:
        assert LLAVE not in local.responder_local(k, ctx)


def test_el_repo_no_contiene_la_llave_y_gitignore_cubre_env():
    gi = (ROOT / ".gitignore").read_text()
    assert ".env" in gi.split() and "*.env" in gi.split()
    assert "ANTHROPIC_API_KEY" not in (ROOT / "config/asistente.json").read_text().replace("variable de entorno ANTHROPIC_API_KEY", "")
    cfg = json.loads((ROOT / "config/asistente.json").read_text())
    assert cfg["modelo"] == "claude-haiku-5-5" and not any("sk-" in str(v) for v in cfg.values())


def _hojas(o):
    if isinstance(o, dict):
        for k, v in o.items():
            yield k
            yield from _hojas(v)
    elif isinstance(o, list):
        for v in o:
            yield from _hojas(v)
    else:
        yield str(o)


def test_el_contexto_no_trae_filas_crudas(res, ctx):
    txt = json.dumps(ctx, ensure_ascii=False, default=str)
    prohibidas = {"raw", "amount_original", "description", "counterparty", "record_id"}
    assert not (prohibidas & set(k for k in _hojas(ctx)))
    # ningun identificador de transaccion ni texto libre de filas del archivo
    # (un ID puede citarse dentro de la ficha de un hallazgo de duplicado; fuera de las fichas, ninguno)
    fuera = json.dumps({k: v for k, v in ctx.items() if k != "hallazgos"}, ensure_ascii=False, default=str)
    assert all(r.transaction_id not in fuera for r in res.records if r.transaction_id)
    assert len([r for r in res.records if r.transaction_id and r.transaction_id in txt]) <= 4
    # solo ubicaciones permitidas dentro de hallazgos
    for h in ctx["hallazgos"]:
        for d in h["donde"]:
            assert set(d) == {"archivo", "hoja", "fila"}
    assert len(txt) < 60_000


@pytest.mark.parametrize("per", list(KEY["consolidado_esperado_usd"]))
def test_las_cifras_del_contexto_coinciden_con_answer_key(res, per):
    c = construir_contexto(res, per, "Datos base")
    exp = KEY["consolidado_esperado_usd"][per]
    got = {k: Decimal(v.replace(",", "")) for k, v in c["cifras"]["consolidado_usd"].items()}
    for k, v in exp["resumen"].items():
        if k in got:
            assert got[k] == Decimal(str(v)).quantize(Decimal("0.01")), (per, k)
    por_cuenta = {x["codigo"]: Decimal(x["consolidado_usd"].replace(",", "")) for x in c["cuentas"]["lista"]}
    for cuenta, v in exp["por_cuenta"].items():
        assert por_cuenta.get(cuenta, Decimal(0)) == Decimal(v), (per, cuenta)


def test_seis_respuestas_locales_no_vacias_y_sin_error_tecnico(ctx):
    assert len(local.PREGUNTAS) == 6
    for k, _ in local.PREGUNTAS:
        t = local.responder_local(k, ctx)
        assert t.strip() and "Traceback" not in t and "falló" not in t.lower()


def test_el_historial_se_envia_y_el_sistema_trae_las_reglas(ctx):
    m = Mock()
    hist = [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}]
    cliente.preguntar(m, ctx, hist, "c")
    sistema, msgs = m.llamadas[0]
    assert [x["content"] for x in msgs] == ["a", "b", "c"]
    assert "no tengo ese dato en la pantalla" in sistema and "NUNCA inventes cifras" in sistema
    assert "CONTEXTO DE LA PANTALLA" in sistema


def _app(seccion="Asistente"):
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120)
    at.run()
    if seccion:
        at.radio(key="nav").set_value(seccion).run()
    assert not at.exception, at.exception
    return at


def test_app_en_modo_local_muestra_6_botones_y_responde_sin_falla():
    at = _app()
    assert not at.exception
    assert at.radio(key="nav").value == "Asistente" and any(o.endswith("Asistente") for o in at.radio(key="nav").options)
    botones = [b for b in at.button if b.key and b.key.startswith("asist_local_")]
    assert len(botones) == 6
    assert len(at.chat_input) == 0
    botones[1].click().run()
    assert not at.exception
    assert not any("falló" in (m.value or "").lower() for m in at.markdown)


def test_app_conectada_muestra_etiqueta_y_cae_a_local_si_falla(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", LLAVE)
    monkeypatch.setattr(cliente, "_CLIENTE_INYECTADO", Mock(falla=True))
    at = _app()
    assert any("impulsado por un modelo de lenguaje" in c.value and "modo conectado" in c.value for c in at.caption)
    assert len(at.chat_input) == 1
    at.chat_input[0].set_value("¿Qué pasó?").run()
    assert not at.exception
    txt = " ".join(x.value for x in list(at.markdown) + list(at.warning) + list(at.error) + list(at.caption))
    assert LLAVE not in txt and "RuntimeError" not in txt and "falló" not in txt.lower()
    assert len([b for b in at.button if b.key and b.key.startswith("asist_local_")]) == 6


def test_app_conectada_responde_y_guarda_historial(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", LLAVE)
    m = Mock()
    monkeypatch.setattr(cliente, "_CLIENTE_INYECTADO", m)
    at = _app()
    at.chat_input[0].set_value("¿Cuál es la utilidad?").run()
    assert not at.exception and len(m.llamadas) == 1
    at.chat_input[0].set_value("¿Y el activo?").run()
    assert [x["content"] for x in m.llamadas[1][1]][:2] == ["¿Cuál es la utilidad?", "Respuesta de prueba (Estados financieros)."]


SECCIONES = ["Inicio", "Estados financieros", "Alertas y errores", "Hallazgos", "Intercompañía", "Trazabilidad",
             "Indicadores", "Variaciones", "Simulador", "Perfiles e integridad", "Ayuda", "Asistente"]


def test_ninguna_seccion_muestra_falló():
    at = _app(None)
    for sec in SECCIONES:
        at.radio(key="nav").set_value(sec).run()
        textos = [x.value for x in list(at.markdown) + list(at.warning) + list(at.error) + list(at.info)]
        assert not at.exception and not any("falló" in t.lower() for t in textos), sec
