# Equipo — Build & Pitch (Open2), UVG, 21 nov 2026

Equipo: **David, Sergio, Mateo, Santiago** (4 personas)

## Roles confirmados

> Decidido en equipo. Ajustado también con feedback directo del organizador (Oscar): los jueces no evalúan diseño/UX — lo que importa es que la solución **funcione** y que se **venda bien** la idea.

| Persona | Rol | Qué hace el día del evento |
|---|---|---|
| **Mateo** | Team Leader | Cara visible del equipo: decide el rumbo cuando hay desacuerdo, mantiene a todos enfocados en el problema real, y es el candidato natural para **dar el pitch** final frente al jurado |
| **Sergio** | Project Manager | Lleva el control del tiempo y el alcance: qué tareas van primero, qué SÍ y qué NO entra al MVP, corre los checkpoints cada 2h (ver abajo) y avisa si algo se está atrasando |
| **Santiago** | Development Manager | Define el stack y la arquitectura técnica (ver [STACK.md](STACK.md)), reparte las tareas de código con David, y resuelve bloqueos técnicos o decide cuándo pedir ayuda a un mentor |
| **David** | Developer | Construye el producto — frontend, backend, o ambos según cómo se repartan Santiago y él el código |

**Nota sobre desarrollo:** con David como único "Developer" explícito, Santiago (Development Manager) probablemente también escribe código — lo normal en equipos de 4 es que el Dev Manager no sea solo gestión, sino que programe junto al Developer y divida frontend/backend entre los dos. Definir esa división (quién lleva frontend, quién backend) apenas se sepa el reto.

**Sobre el pitch:** aunque Mateo es el candidato natural por ser Team Leader, cualquiera puede apoyar en partes del pitch (ej. Sergio presentando el "por qué" de las decisiones de producto). Definir el reparto exacto en el bloque "Preparar el pitch" del cronograma (ver [PLAN.md](PLAN.md)).

## Qué SÍ importa y qué NO (feedback del organizador)

- **Importa:** que la solución funcione de verdad y resuelva el problema planteado. Que el pitch venda bien esa idea.
- **No importa (para el MVP de un día):** que se vea con diseño pulido/UX cuidado — eso es lo de menos para calificar.
- **No perder tiempo en:** sistemas de login/registro de usuario con contraseña real. Ejemplo que dio el organizador: mucha gente pierde horas metiendo autenticación "que funcione" cuando no es lo que califican — eso se agrega después, si sobra tiempo. Usar un usuario de prueba fijo o simular el login si hace falta mostrarlo.

## Reglas básicas de trabajo en equipo

### Comunicación
- Un solo canal de chat para todo el día (WhatsApp/grupo ya existente). Nada de decisiones importantes solo de palabra sin avisar al grupo.
- Si alguien se traba más de 15-20 min en algo, pide ayuda en el chat/al equipo en vez de seguir solo.
- Decisiones de alcance (qué se corta del MVP) las define Sergio (Project Manager), pero se avisan a todos.

### Cómo dividir tareas
- Nadie trabaja "a ciegas": cada tarea se anota en una lista compartida (Notion, Google Doc, o incluso un papel) con nombre de quien la lleva.
- Evitar que dos personas toquen el mismo código/archivo al mismo tiempo sin coordinarse (usar ramas de git si aplica).
- Tareas chicas y claras > tareas grandes y ambiguas. Si una tarea dura más de 1 hora sin avance, se reevalúa.

### Checkpoints
- Checkpoint rápido (5-10 min) cada **2 horas** durante el Build: qué llevo, qué sigue, qué bloqueos tengo.
- Checkpoint obligatorio a medio Build: decidir si el alcance del MVP sigue siendo realista o hay que recortar.
- Checkpoint final antes del pitch: validar que la demo funciona de principio a fin (ver checklist en [PLAN.md](PLAN.md)).

### Manejo de conflictos / bloqueos
- Si hay desacuerdo técnico y no se resuelve rápido, decide Santiago (Development Manager); si es un desacuerdo de rumbo/producto, decide Mateo (Team Leader) — para no perder tiempo votando todo.
- Preferir "hacerlo simple y que funcione" sobre "hacerlo perfecto" — es un día, no un producto final.
