# Plan del día — Build & Pitch (Open2), UVG, 21 nov 2026

> Cronograma asumiendo Build de **7 horas** (ajustable a 6-8h según horario real que anuncien). Ajustar horas de inicio reales el día del evento.
>
> **Verificado en open2.io/build-and-pitch (2026-11-06):** el horario exacto de ese día AÚN NO está publicado — la página oficial dice "el horario exacto sale con el registro". Esta tabla es una plantilla de ejemplo con los mismos bloques que anuncia Open2 (Llegada → Kickoff → Equipos → Build → Pitch → Cierre); **hay que reemplazar las horas en cuanto Open2 publique el horario real** (revisar el registro en Open2App).

## Checklist pre-evento (antes del 21 de noviembre)

> Checklist del equipo para los días previos — complementa el checklist de "antes del pitch" más abajo, que es para el día mismo.

### 1. Organización
- [x] Confirmar los 4 integrantes (David, Sergio, Mateo, Santiago)
- [x] Identificar las habilidades de cada uno
- [x] Asignar roles y responsabilidades — ver [TEAM.md](TEAM.md): Mateo (Team Leader), Sergio (Project Manager), Santiago (Development Manager), David (Developer)
- [ ] Establecer horarios de trabajo y reuniones previas al evento (al menos 1 sesión de equipo antes del 21 nov)

### 2. Proyecto
- [ ] Definir posibles ideas — brainstorm libre del equipo antes del evento, sin depender del reto (ideas "comodín" adaptables)
- [ ] Identificar el problema que queremos resolver — ideas enfocadas en problemas reales de Guatemala (ver nota del formato del evento)
- [ ] Elegir tecnologías y herramientas — ya definido en [STACK.md](STACK.md) (Next.js + Supabase + Vercel + alternativas)
- [ ] Definir qué queremos construir — se decide en el Kickoff una vez se sepa el reto, ver bloque "Definir idea" en el cronograma
- [ ] Investigar los criterios de evaluación — feedback ya recibido de Oscar (organizador): no califican diseño/UX, importa que **funcione** y que el pitch **venda** la idea (ver [TEAM.md](TEAM.md))

### 3. Preparación técnica
- [ ] Familiarizarnos con GitHub y herramientas de IA (ej. Claude Code, Cursor, v0, Lovable) — repartir quién prueba qué antes del evento
- [ ] Preparar computadoras y programas: Node.js, Git, editor de código, cuenta de GitHub y de Supabase ya creadas
- [ ] Practicar el trabajo en equipo — idealmente un mini-ensayo de "armar algo juntos" antes del día real (aunque sea 1-2 horas)
- [ ] Definir una estrategia para la competencia — priorizar que funcione > que se vea bonito (ver nota en [TEAM.md](TEAM.md))

### 4. Día del evento
- [ ] Documento de identificación (DPI) de cada integrante
- [ ] Laptops y cargadores de los 4
- [ ] Datos móviles (hotspot) por si falla el wifi del venue
- [ ] Agua y snacks
- [ ] Registro hecho en Open2App antes de llegar: [app.open2.io/nr3qt0gh](https://app.open2.io/nr3qt0gh)

## Cronograma hora por hora

| Hora (ejemplo) | Bloque | Qué hacer |
|------|--------|-----------|
| 8:00 – 8:30  | Llegada / registro | Check-in, conseguir wifi, ubicar mentores, sentarse como equipo |
| 8:30 – 9:00  | Kickoff | Anuncian el reto. **Todos escuchan y toman notas** (no hablar entre el equipo todavía) |
| 9:00 – 9:30  | Formación de equipos / reconfirmación | Ya estamos formados (David, Sergio, Mateo, Santiago) — usar este tiempo para releer el reto y aclarar dudas con organizadores |
| 9:30 – 10:30 | **Definir idea** | Brainstorm rápido, elegir UNA idea, definir quién es el usuario, qué problema resuelve, qué hace el MVP (y qué NO hace). Asignar roles (ver [TEAM.md](TEAM.md)) |
| 10:30 – 13:30 | **Armar MVP (parte 1)** | Desarrollo central: setup del stack ([STACK.md](STACK.md)), features core, deploy inicial funcionando aunque sea feo |
| 13:30 – 14:00 | Almuerzo | Comer, no seguir codeando en la mesa si se puede evitar — recargar energía |
| 14:00 – 16:30 | **Armar MVP (parte 2)** | Terminar features clave, conectar frontend-backend, empezar a pulir lo visual, probar flujo completo |
| 16:30 – 17:15 | **Preparar el pitch** | Armar slides/demo, definir quién dice qué, llenar [PITCH.md](PITCH.md) |
| 17:15 – 17:45 | **Ensayar el pitch** | Mínimo 2 corridas completas con cronómetro (3-5 min), ajustar timing, grabar la demo como backup en video |
| 17:45 – 18:00 | Buffer / checklist final | Ver checklist abajo, resolver imprevistos de último minuto |
| 18:00 (hora del pitch) | **Pitch** | Presentación final |
| Después | Cierre | Networking, feedback, celebrar 🎉 |

**Checkpoints de equipo** (cada 2h aprox, ver [TEAM.md](TEAM.md)): ~10:30, ~12:30, ~14:30, ~16:30 (este último es el de "vamos a tiempo para el pitch").

## Checklist: qué necesitamos tener listo antes de la hora del pitch

### Producto
- [ ] La demo corre sin errores en un flujo completo (de inicio a fin)
- [ ] Deploy funcionando en una URL pública (no depender de `localhost` en el pitch)
- [ ] Datos de prueba/mock cargados para que la demo se vea "real" (no vacía)
- [ ] Plan B: video grabado de la demo funcionando, por si falla internet/el deploy en vivo

### Pitch
- [ ] Guion del pitch lleno ([PITCH.md](PITCH.md)) con tiempos por sección
- [ ] Asignado quién habla en cada parte
- [ ] Ensayado al menos 2 veces completo con cronómetro
- [ ] Slides (si se usan) listas y en un dispositivo que funcione, con backup en USB/drive

### Logística
- [ ] Cargadores/baterías extra para laptops y celular (para la demo)
- [ ] Alguien asignado a manejar las preguntas del jurado después del pitch
- [ ] Repositorio/código subido (GitHub o similar) por si lo piden
- [ ] Revisar reglas específicas del reto/sponsor una vez se anuncien (sponsors confirmados en la web al 2026-11-06: **Notion, Supabase, Elipsis Studio**; "+ más por anunciar" — confirmar en el evento si hay otros)
