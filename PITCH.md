# Pitch (3-5 minutos) — BORRADOR DE PRÁCTICA

> Track: problemas ambientales y sostenibilidad. Idea de práctica: ahorro de luz y agua en hogares guatemaltecos.
> Lo marcado con **[VERIFICAR]** es un dato que hay que investigar antes de decirlo en voz alta. No inventar cifras.

**Nombre del proyecto:** ___________________________ (ideas: Ahorra+, Foco y Gota, Recibo Claro)

**Quién presenta cada parte:** Mateo (apertura, problema, cierre) · Santiago/David (demo) · Sergio (por qué nosotros, próximos pasos) — ajustar tras el primer ensayo

---

## 1. Problema (~30-45 seg)

**Usuario:** hogares guatemaltecos.
**Dolor:** pagan de más en luz y agua por consumo innecesario (aparatos encendidos, fugas, hábitos) y no se enteran hasta que llega el recibo, cuando ya no hay nada que hacer.

```
Frase de apertura: "Cada mes llega el recibo de luz y de agua, y casi nadie sabe en qué se le fue el dinero."
- Gasto innecesario que sufre la familia guatemalteca: [VERIFICAR: cuánto paga en promedio un hogar por luz y agua, en Q]
- Ese consumo innecesario también es desperdicio de energía y agua: conecta con sostenibilidad.
- Hoy el recibo solo dice cuánto, no dice qué hacer para bajarlo.
```

## 2. Solución (~30-45 seg)

```
"Hacemos una herramienta web donde el hogar ingresa su consumo de luz y agua
y recibe, en segundos, cuánto está gastando de más y 3 acciones concretas
para ahorrar, con el ahorro estimado en quetzales."
```

- Entrada simple: consumo del recibo + datos básicos del hogar.
- Salida clara: gasto actual, ahorro potencial en Q, top 3 acciones.
- Impacto ambiental como bono: kWh y m³ ahorrados y CO2 evitado.

## 3. Demo (~90-120 seg) — la parte más importante

```
Paso 1: El usuario ingresa consumo del mes (kWh de luz y m³ de agua) y cuántas personas viven en el hogar.
Paso 2: La herramienta muestra cuánto gasta en Q y cuánto podría ahorrar.
Paso 3: Muestra las 3 recomendaciones con ahorro estimado en Q cada una, y el impacto ambiental (kWh, m³, CO2).
```

Demo sin login: usuario de prueba fijo, datos de ejemplo precargados.
**Plan B si falla la demo en vivo:** video de respaldo ubicado en: ___________________

## 4. Por qué nosotros (~20-30 seg)

```
[Espacio para llenar: experiencia del equipo construyendo webs rápido, entendimiento del usuario guatemalteco, equipo con roles definidos]
```

## 5. Próximos pasos (~20-30 seg)

```
- Leer el recibo con foto (OCR) para no teclear nada
- Tarifas reales por distribuidora [VERIFICAR: EEGSA, Energuate, etc.]
- Alertas mensuales y seguimiento del ahorro en el tiempo
- Versión para negocios pequeños
```

## Cierre (1 frase memorable)
```
[Espacio para llenar. Idea: "Que el recibo deje de ser una sorpresa y se vuelva un plan."]
```

---

## Alcance del MVP (qué SÍ y qué NO)

**SÍ (hoy):**
- Una pantalla de entrada: personas en el hogar, kWh/mes, m³/mes.
- Cálculo de gasto en Q con tarifas simples (tabla fija en el código, marcada como estimación).
- Resultado: ahorro potencial + 3 recomendaciones tomadas de una tabla de reglas (por ejemplo: consumo alto de luz para el tamaño del hogar, recomendar focos LED, desconectar aparatos en standby, revisar fugas si el agua es alta).
- CO2 evitado con un factor de emisión fijo [VERIFICAR: factor de emisión de la red eléctrica de Guatemala].
- Supabase (opcional): guardar cada cálculo para mostrar un historial en la demo.

**NO (después):**
- Login y registro de usuarios (indicación de Oscar).
- Lectura de recibos con foto.
- Tarifas exactas por distribuidora.
- Diseño pulido: solo que se entienda.

**Opcional si sobra tiempo:** usar un LLM para redactar las recomendaciones en lenguaje natural a partir de los números.

**Reparto sugerido del MVP:**
- Santiago: estructura del proyecto, tabla de reglas y lógica de cálculo.
- David: pantalla de entrada y de resultados, conexión con Supabase.
- Sergio: tabla de tarifas y recomendaciones investigadas y verificadas, control de tiempo.
- Mateo: problema, guion del pitch, datos para la apertura.

---

## Notas de ensayo
- Tiempo total objetivo: _____ min _____ seg
- Cosas que salieron bien en el ensayo: ___________________________
- Cosas a mejorar antes del pitch real: ___________________________
- Preguntas esperadas del jurado y respuesta corta:
  - Q: ¿De dónde salen los números? A: ___________________
  - Q: ¿Cómo sabe que el ahorro es real? A: ___________________
  - Q: ¿Cómo ganan dinero / quién lo usaría a escala? A: ___________________
