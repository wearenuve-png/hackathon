"""Contrato compartido: todas las reglas devuelven una lista de Hallazgo.

Esquema normalizado (una fila por partida), columnas obligatorias:
    archivo, empresa, periodo (YYYY-MM), concepto, tipo, monto, fila
Columnas opcionales:
    moneda      moneda declarada de la partida (GTQ/MXN/USD)
    contraparte empresa con la que se hizo la operacion (intercompania)
    grupo       a que grupo suma una partida; las filas con tipo 'total' llevan el grupo que totalizan

tipo permitido: ingreso, costo, gasto, utilidad, activo, pasivo, patrimonio,
                venta_ic, compra_ic, total
"""
from dataclasses import dataclass, asdict

BLOQUEANTE = "BLOQUEANTE"
ADVERTENCIA = "ADVERTENCIA"
INFO = "INFO"

COLUMNAS = ["archivo", "empresa", "periodo", "concepto", "tipo", "monto", "fila",
            "moneda", "contraparte", "grupo"]
TIPOS = {"ingreso", "costo", "gasto", "utilidad", "activo", "pasivo",
         "patrimonio", "venta_ic", "compra_ic", "total"}


@dataclass
class Hallazgo:
    empresa: str
    archivo: str
    fila: object          # fila de origen (o lista/rango de filas)
    columna: str
    regla: str
    severidad: str
    mensaje: str
    valor_encontrado: object = None
    valor_esperado: object = None
    sugerencia: str = ""

    def dict(self):
        return asdict(self)
