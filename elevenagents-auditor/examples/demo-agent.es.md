# Auditoría de agente ElevenAgents

**Agente:** Demo - Sol, onboarding de Tiendalia (rioplatense)  
**Fecha:** 2026-10-19  
**Configuración leída:** language `es` · LLM `gpt-6-luna` · TTS `eleven_flash_v2_5` · voice `Melody - Ecommerce Voice`

## Puntaje general: 95/100 — Listo para escalar

| Dimensión | Puntaje | |
|---|---:|---|
| Estructura del prompt | 100/100 | ██████████ |
| Primer mensaje | 100/100 | ██████████ |
| Idioma y voz | 100/100 | ██████████ |
| Modelos y latencia | 100/100 | ██████████ |
| Turnos e interrupciones | 100/100 | ██████████ |
| Herramientas | no aplica |  |
| Base de conocimiento | no aplica |  |
| Guardrails y datos sensibles | 80/100 | ████████░░ |
| Evaluación y recolección de datos | 83/100 | ████████░░ |
| Duración y cierre de la llamada | 100/100 | ██████████ |

## Prioridades (de mayor a menor impacto)

1. **Quién puede iniciar conversaciones** (media) — Agente público sin lista de dominios: cualquiera con el id puede abrir sesiones y consumir créditos. Para un widget en la web, agregá el dominio del cliente a la allowlist; para apps, usá URLs firmadas.
2. **Pruebas automáticas** (baja) — Sin pruebas ni simulaciones adjuntas: cada cambio al prompt se prueba a mano. Guardá 3 a 5 conversaciones difíciles como pruebas y corrélas antes de cada cambio.

## Detalle por dimensión

### Estructura del prompt · 100/100

- ✅ **Sección de rol o personalidad** — El prompt tiene una sección explícita de rol o personalidad.
- ✅ **Sección de objetivo** — El prompt tiene una sección explícita de objetivo.
- ✅ **Sección de tono** — El prompt tiene una sección explícita de tono.
- ✅ **Sección de límites (guardrails)** — El prompt tiene una sección explícita de límites (guardrails).
- ✅ **Sección de manejo de errores** — El prompt tiene una sección explícita de manejo de errores.
- ✅ **Sección de derivación a una persona** — El prompt tiene una sección explícita de derivación a una persona.
- ✅ **Largo del prompt** — Largo razonable (5682 caracteres).
- ✅ **Estilo para voz: respuestas cortas** — El prompt pide respuestas cortas o una pregunta por vez.
- ✅ **Sin formato visual en la voz** — El prompt evita listas, emojis o formato que la voz no puede leer.

### Primer mensaje · 100/100

- ✅ **Primer mensaje** — Hay primer mensaje.
- ✅ **Largo del saludo** — Saludo breve (137 caracteres).
- ✅ **Transparencia: se presenta como IA** — El saludo deja claro que es un asistente virtual.
- ✅ **Termina invitando a hablar** — El saludo cierra con una pregunta.

### Idioma y voz · 100/100

- ✅ **Modelo de voz compatible con el idioma** — 'eleven_flash_v2_5' soporta 'es'.
- ✅ **Idioma del prompt y del agente** — Prompt y agente en el mismo idioma.
- ✅ **Voz nativa del idioma del agente** — Voz 'Melody - Ecommerce Voice' apta para 'es'.
- ✅ **Acento de la voz y región del público** — Acento 'argentine' coherente con es-AR.
- ✅ **Voz verificada para ese modelo** — La voz está verificada en ese idioma con ese modelo.
- ✅ **Variante rioplatense coherente** — Voz argentina y textos con voseo: el agente suena local de punta a punta.

### Modelos y latencia · 100/100

- ✅ **Generación del LLM** — LLM actual: 'gpt-6-luna'.
- ✅ **Modelo de voz para tiempo real** — 'eleven_flash_v2_5' es apto para tiempo real.
- ✅ **Temperatura** — Temperatura 0.3.

### Turnos e interrupciones · 100/100

- ✅ **Espera antes de retomar la palabra** — 7.0 s, dentro del rango recomendado.
- ✅ **Muletilla de espera en el idioma del agente** — Muletilla de espera activa y localizada.
- ✅ **Palabras clave para el reconocimiento de voz** — 4 palabras clave cargadas (marcas, productos).

### Herramientas · no aplica

- ➖ **Herramientas de negocio** — Sin herramientas propias: está bien para un agente informativo; para casos transaccionales, conectá webhooks o MCP.

### Base de conocimiento · no aplica

- ➖ **Base de conocimiento** — El conocimiento está escrito dentro del prompt, en su propia sección. Bien mientras sea corto; si crece, pasalo a la base de conocimiento.

### Guardrails y datos sensibles · 80/100

- ✅ **Guardrails de la plataforma** — Foco y protección contra prompt injection activados.
- ✅ **Nunca pedir datos sensibles** — El prompt menciona qué datos sensibles no pedir.
- ✅ **Retención de conversaciones** — Retención de 30 días.
- ❌ **Quién puede iniciar conversaciones** — Agente público sin lista de dominios: cualquiera con el id puede abrir sesiones y consumir créditos.  
  → Para un widget en la web, agregá el dominio del cliente a la allowlist; para apps, usá URLs firmadas.
- ✅ **Tope diario de conversaciones** — Tope diario: 50.

### Evaluación y recolección de datos · 83/100

- ✅ **Criterios de evaluación** — 5 criterios de éxito definidos.
- ✅ **Recolección de datos** — 4 campo(s) estructurado(s) por conversación.
- ❌ **Pruebas automáticas** — Sin pruebas ni simulaciones adjuntas: cada cambio al prompt se prueba a mano.  
  → Guardá 3 a 5 conversaciones difíciles como pruebas y corrélas antes de cada cambio.

### Duración y cierre de la llamada · 100/100

- ✅ **El agente puede terminar la llamada** — Herramienta end_call activa.
- ✅ **El prompt dice cuándo cerrar** — El prompt describe el cierre de la llamada.
- ✅ **Duración máxima** — Máximo de 10 minutos.
- ✅ **Mensaje al llegar al máximo** — Hay un mensaje de cierre por tiempo.
- ✅ **Silencio prolongado** — Las llamadas abandonadas tienen salida.

## Notas

- Región del público considerada: es-AR.

---
*Generado con elevenagents-auditor. La rúbrica y el porqué de cada regla están en el README.*
