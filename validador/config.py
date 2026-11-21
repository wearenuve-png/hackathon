"""Parametros editables. Las tasas son 'unidades de moneda por 1 USD'."""

TASAS = {"USD": 1.0, "GTQ": 8.0, "MXN": 20.0}

# Rango razonable de cada tasa (para detectar una tasa mal escrita, ej. 80 en vez de 8)
RANGO_TASAS = {"GTQ": (7.0, 9.0), "MXN": (15.0, 25.0)}

# Controles que DEBEN poder correr sobre cada empresa. Si uno no puede correr
# (faltan datos para verificarlo), la empresa NO pasa: "sin verificar" no es "bien".
CONTROLES_OBLIGATORIOS = ["moneda", "balance", "totales", "utilidad", "razonabilidad"]

# Cuanto puede desviarse una razon observada de una tasa para decir "parece esa moneda"
TOLERANCIA_TASA = 0.15
# Diferencia relativa aceptada al cuadrar totales / balance / intercompania
TOLERANCIA_REL = 0.005
# Variacion contra el historial que dispara una advertencia (veces)
FACTOR_RAZONABILIDAD = 2.5
# Meses esperados por empresa en el presupuesto
MESES_ESPERADOS = 12
