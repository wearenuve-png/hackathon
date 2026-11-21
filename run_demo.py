from validador.datos_demo import generar
from validador.motor import validar, puerta, reporte_texto, registrar_auditoria

df, ref = generar()
hallazgos, semaforo = validar(df, ref)
print(reporte_texto(hallazgos, semaforo))

pasan, ok = puerta(df, semaforo)
print(f"\nPasan al consolidado: {ok or 'ninguna'}")
registrar_auditoria("auditoria.jsonl", "demo", "validacion", {"semaforo": semaforo, "pasan": ok})
