"""Cliente del asistente (modo conectado). La llave sale SOLO de la variable de entorno ANTHROPIC_API_KEY: nunca se
escribe en el repositorio, en archivos de configuracion, en logs ni en pantalla. Si no hay llave, no hay red o falla
cualquier cosa, el asistente cae al modo local: al usuario nunca se le muestra un error tecnico."""
import json
import os
from typing import List, Optional

from .config import cargar_config

SYSTEM = """Eres el asistente contable de NEXUS, un motor de consolidación financiera multiempresa.
Reglas:
- Responde siempre en español, claro y simple, orientado a contabilidad, para alguien que no es experto.
- Responde SOLO con el contexto de la pantalla que se te entrega abajo. No uses conocimiento externo para dar cifras.
- Cita de dónde sale cada cifra: la pestaña (por ejemplo «Estados financieros», «Variaciones») o la ficha (por ejemplo FCH-003).
- NUNCA inventes cifras. Si el dato no está en el contexto, di exactamente: «no tengo ese dato en la pantalla».
- No corriges datos ni apruebas nada: eso lo hace una persona con los botones de la app. Si te lo piden, explica cómo se hace.
- Si te piden algo fuera de contabilidad o de NEXUS, redirige amablemente hacia lo que sí puedes explicar.
- Las estimaciones y los supuestos se presentan como lo que son (ESTIMACIÓN, SUPUESTO); no los presentes como hechos.
- Nunca atribuyas un error a una persona: habla de datos, archivos y procesos, y de causas probables."""

# solo para pruebas: un cliente simulado que reemplaza al real (siempre se exige que exista la llave)
_CLIENTE_INYECTADO = None


class AsistenteNoDisponible(Exception):
    pass


def llave() -> str:
    return (os.environ.get("ANTHROPIC_API_KEY") or "").strip()


def redactar(texto, secreto: Optional[str] = None) -> str:
    """Quita la llave de cualquier texto antes de mostrarlo."""
    s = "" if texto is None else str(texto)
    k = secreto if secreto is not None else llave()
    return s.replace(k, "[llave oculta]") if k else s


class ClienteAnthropic:
    """Envoltorio fino del SDK `anthropic` (import perezoso: es una dependencia OPCIONAL)."""

    def __init__(self, api_key: str, modelo: str, max_tokens: int, timeout_s: int):
        import anthropic  # ImportError -> el asistente queda en modo local
        self._client = anthropic.Anthropic(api_key=api_key, timeout=timeout_s)
        self.modelo, self.max_tokens = modelo, max_tokens

    def __repr__(self) -> str:                      # nunca imprime la llave
        return f"ClienteAnthropic(modelo={self.modelo!r})"

    def responder(self, system: str, mensajes: List[dict]) -> str:
        resp = self._client.messages.create(model=self.modelo, max_tokens=self.max_tokens, system=system,
                                            messages=mensajes)
        return "".join(getattr(b, "text", "") for b in resp.content).strip()


def obtener_cliente(cfg_path=None):
    """Cliente conectado o None (modo local). Apagado por defecto: requiere ANTHROPIC_API_KEY."""
    if not llave():
        return None
    if _CLIENTE_INYECTADO is not None:
        return _CLIENTE_INYECTADO
    cfg = cargar_config(cfg_path)
    try:
        return ClienteAnthropic(llave(), cfg["modelo"], cfg["max_tokens"], cfg["timeout_s"])
    except Exception:  # noqa: BLE001 - sin SDK o sin red: modo local, sin mensajes tecnicos
        return None


def sistema_con_contexto(ctx: dict) -> str:
    return (SYSTEM + "\n\nCONTEXTO DE LA PANTALLA (JSON ya calculado por NEXUS; es lo único que sabes):\n"
            + json.dumps(ctx, ensure_ascii=False, default=str))


def preguntar(cliente, ctx: dict, historial_api: List[dict], pregunta: str, max_historial: int = 20) -> str:
    """Una vuelta de conversacion: historial + pregunta nueva. Devuelve texto sin la llave."""
    mensajes = list(historial_api)[-max_historial:] + [{"role": "user", "content": pregunta}]
    while mensajes and mensajes[0]["role"] != "user":
        mensajes.pop(0)
    texto = cliente.responder(sistema_con_contexto(ctx), mensajes)
    if not texto or not texto.strip():
        raise AsistenteNoDisponible("respuesta vacia")
    return redactar(texto)
