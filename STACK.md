# Stack técnico sugerido — rápido de armar en pocas horas

> No sabemos el reto todavía, así que esto es una base flexible, priorizando velocidad de desarrollo y deploy sobre "lo más robusto". Ajustar según lo que pida el reto (ej. si es más de datos, IA, e-commerce, etc.)
>
> **Verificado en open2.io/build-and-pitch (2026-11-06):** Supabase sí es sponsor confirmado — buena señal para este stack. Los sponsors que aparecen en la web oficial son **Notion, Supabase y Elipsis Studio** (media partner), con "+ más por anunciar". No encontré a SpaceX ni Grupo AG listados ahí todavía — si tenían esa info de otra fuente, conviene confirmarla antes del evento (puede que Open2 aún no haya actualizado la página).

## Stack principal recomendado

**Next.js + Supabase + Vercel**

- **Next.js** (React): frontend + backend (API routes) en un solo proyecto, fácil de spinnear rápido con `create-next-app`.
- **Supabase**: base de datos Postgres + autenticación + storage de archivos, todo con un dashboard listo en minutos. **Es patrocinador del evento** → revisar en su mesa/booth si dan créditos, soporte en vivo de mentores, o algún beneficio especial para el equipo.
- **Vercel**: deploy del frontend/Next.js con un `git push`, gratis para proyectos chicos, da URL pública al instante (clave para la demo y el pitch).
- **Tailwind CSS**: para que se vea decente rápido sin pelear con CSS desde cero.

### Por qué este combo
- Un solo lenguaje (TypeScript/JavaScript) de punta a punta → menos context-switching con 4 personas.
- Deploy en minutos, no horas → más tiempo para producto y menos para DevOps.
- Supabase da base de datos + auth + storage sin montar servidores → ideal para 6-8 horas.

## Alternativas rápidas (según el reto)

| Si el reto es sobre... | Considerar |
|---|---|
| Landing / producto simple sin backend complejo | Next.js + Vercel solo (sin Supabase), o incluso una landing estática |
| Mucho uso de IA / chat / agentes | Next.js + Supabase + API de algún LLM (revisar si algún sponsor da créditos de IA) |
| App más simple, sin tiempo ni para Next.js | Lovable / v0 / Bolt (generan UI + lógica básica rapidísimo) + Supabase como backend |
| Automatización / flujos (fit con experiencia en automatizaciones) | Next.js + Supabase + algo tipo n8n/Make/Zapier si aplica, o simplemente funciones serverless en Vercel |
| Mobile-first | Next.js responsive (PWA) antes que meterse a nativo — no hay tiempo para app nativa en 7 horas |

## Checklist de setup (primeros 30-45 min del Build)

- [ ] `npx create-next-app@latest` con TypeScript + Tailwind
- [ ] Repo en GitHub creado y conectado desde el inicio (commits frecuentes)
- [ ] Proyecto de Supabase creado, URL + API key guardadas en `.env.local`
- [ ] Deploy inicial a Vercel funcionando (aunque sea una página en blanco) — así el pipeline de deploy ya está probado antes de necesitarlo con prisa
- [ ] Definir 2-3 tablas máximo en Supabase para el MVP (no sobre-diseñar el modelo de datos)
- [ ] Pasar por el booth/mentores de Supabase apenas se pueda — preguntar por créditos y soporte

## Reglas para no perder tiempo
- No instalar librerías "por si acaso" — solo lo que se use ya.
- Si algo no funciona en 20-30 min, buscar ayuda de un mentor en vez de seguir solo.
- MVP > producto bonito. Funcionalidad end-to-end simple gana sobre features a medias.
