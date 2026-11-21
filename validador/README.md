# validador/ — prototipo anterior (SOLO REFERENCIA)

Primer prototipo del validador, hecho antes del brief NEXUS. **No forma parte del flujo**: ni `nexus/`, ni
`app.py`, ni `scripts/` lo importan (una prueba lo verifica).

No usarlo ni extenderlo: trabaja con `float` y con supuestos que el brief prohíbe (infiere la moneda por el
tamaño del importe, bloquea todo duplicado). El validador vigente es `nexus/validation.py`.

Se conserva por las ideas de reglas (totales, balance, razonabilidad). `run_demo.py` en la raíz es el demo de
este prototipo.
