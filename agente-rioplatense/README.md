# Sol: a Rioplatense onboarding agent for ElevenAgents

A demo voice agent in **Argentine (Rioplatense) Spanish** that onboards new customers of a SaaS platform. It is designed around one adoption metric, **activation**, rather than around answering questions.

> **Tiendalia is a fictional company.** It is a small-business online-store platform invented for this demo. No customer data, third-party content or real brand is used.

| File | What it is |
|---|---|
| [`prompt.md`](prompt.md) | The full system prompt, readable as a document |
| [`config.json`](config.json) | The `POST /v1/convai/agents/create` payload (generated from `prompt.md`) |
| [`voz.json`](voz.json) | Metadata of the chosen voice, used by the auditor offline |
| [`scripts/build_config.py`](scripts/build_config.py) | Rebuilds `config.json` from `prompt.md` and the settings |
| [`scripts/crear_agente.py`](scripts/crear_agente.py) | Creates the agent in your workspace (refuses to duplicate; no phone number, no public link) |

Audit result with [`elevenagents-auditor`](../elevenagents-auditor): **95/100**, with no critical or high-severity gaps ([report](../elevenagents-auditor/examples/demo-agent.en.md)). The two open items are deliberate and explained below.

## The use case

New customers who signed up but haven't sold yet are the classic time-to-value gap. Sol calls (or is called from the dashboard widget) and walks the person through the four activation steps, **one at a time, while they do it**:

1. Load at least three products (photo, price, stock)
2. Set up a payment method
3. Set up shipping or pickup
4. Publish the store

Success is not "the user understood the platform". It is "the user finished one more step during the call".

## Design decisions

**Built for an activation metric.** The goal section is a funnel, not a FAQ. The agent asks one question to find the current step, guides the next one, and uses the `skip_turn` system tool to wait in silence while the person does it ("dale, te espero"). It ends every call by naming the single next pending step. One step done is worth more than four explained.

**Rioplatense, end to end.** The voice is Argentine and so is the grammar. The prompt asks for *voseo* explicitly ("vos tenés", "fijate") and forbids *tú*. An Argentine accent reading neutral Spanish sounds off to local users. The greeting and every message (timeout filler, time-limit and silence messages) are localized too. The platform default filler is in English, which is a common miss.

**Voice: "Melody – Ecommerce Voice" (ElevenLabs Voice Library).** Female, Argentine accent, labelled *informative/educational*, described as warm, clear and trustworthy for guiding users on online sales platforms. It is verified for Spanish (es-AR) on `eleven_flash_v2_5`, and I had already used it in earlier live demos with Argentine audiences. For onboarding, clarity and patience matter more than expressiveness.

**Latency first.** TTS `eleven_flash_v2_5` (~75 ms model latency per the docs). LLM `gpt-6-luna`, one of the two general-purpose starting points recommended in the ElevenLabs prompting guide, at temperature 0.3 for consistent step-by-step guidance and with no reasoning budget. Any model change should be benchmarked on real calls.

**Structure the model can follow.** Headed sections in the order the prompting guide recommends: Personality, Environment, Tone, Goal, Product knowledge, Tools, Error handling, Escalation, Guardrails and Closing. Critical lines are marked as important. The product knowledge is short, so it lives in the prompt. If it grew past a couple of pages, it would move to the knowledge base with RAG.

**Honest about limits.** The agent can't see the user's screen or account, and the prompt says so. If the panel looks different from what it describes, it doesn't insist: it hands off. It never invents features, prices, timelines or policies.

**Escalation with a reason and a place.** Billing, account access, payments not credited, two failed guided attempts, or an upset user all go to the in-app support chat. The agent says why, where the button is and the support hours, and offers to continue with another step meanwhile.

**Guardrails.**
- In the prompt: never ask for or accept passwords, verification codes, card numbers, CBU/CVU (Argentine bank account identifiers), national ID or bank details, and interrupt politely if the user starts reading them out. No promises about sales or payout times, no tax or legal advice, no competitor talk, no prompt disclosure.
- On the platform: *focus* and *prompt-injection* guardrails on; 30-day conversation retention; a daily cap of 50 conversations and 2 concurrent (it's a demo); no phone number attached.

**Measurable from day one.**
- *Evaluation criteria:* a step was completed; the call closed with a clear next step; no invented information; correct escalation; no sensitive data requested.
- *Data collection, with no personal data:* onboarding stage at the end of the call, steps completed in the call, main blocker, and whether the call was escalated.

Aggregated, these fields answer the adoption questions that matter: where people get stuck (photos? payments?), how many steps a call moves, and how often a human is needed.

**Call lifecycle.** `end_call` enabled with clear rules for when to use it, a 10-minute maximum with a closing message, and a 45-second silence timeout with a goodbye.

## Deliberately left open (and flagged by the auditor)

- **Domain allowlist.** In production, the customer's domain goes in the allowlist (or the app uses signed URLs). It's off here so the demo can be tested from the ElevenLabs dashboard.
- **Attached tests.** The next step is to save three to five hard conversations (an upset user, a user reading out a card number, a question outside the knowledge) as simulation tests.

## Recreate it

```bash
python3 scripts/build_config.py           # after editing prompt.md
export ELEVENLABS_API_KEY=...             # never commit it
python3 scripts/crear_agente.py           # creates it once; the id goes to privado/, which git ignores
```

---

## En español

**Sol** es una agente de voz de demostración, en español rioplatense, que acompaña a clientes nuevos de una plataforma de tiendas online (**Tiendalia, empresa ficticia**) a activar su cuenta: cargar tres productos, configurar el cobro, configurar el envío y publicar. Está diseñada para una métrica de adopción, la activación, no para responder preguntas. Guía un paso por vez, espera en silencio mientras la persona lo hace (herramienta `skip_turn`) y siempre cierra con el próximo paso pendiente.

Decisiones principales: voz argentina ("Melody – Ecommerce Voice") y voseo explícito en el prompt; modelo de voz de baja latencia (`eleven_flash_v2_5`); prompt por secciones según la guía oficial; derivación al chat de soporte con motivo, lugar y horario; nunca pide contraseñas, tarjetas, CBU, CVU ni DNI; cinco criterios de evaluación y cuatro campos de datos sin información personal; retención de 30 días y topes de uso. El auditor le da 95/100; las dos brechas abiertas (lista de dominios y pruebas automáticas) son decisiones conscientes de una demo.
