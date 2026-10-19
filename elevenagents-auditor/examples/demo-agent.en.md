# ElevenAgents agent audit

**Agent:** Demo - Sol, onboarding de Tiendalia (rioplatense)  
**Date:** 2026-10-19  
**Configuration read:** language `es` · LLM `gpt-6-luna` · TTS `eleven_flash_v2_5` · voice `Melody - Ecommerce Voice`

## Overall score: 95/100 — Ready to scale

| Dimension | Score | |
|---|---:|---|
| Prompt structure | 100/100 | ██████████ |
| First message | 100/100 | ██████████ |
| Language and voice | 100/100 | ██████████ |
| Models and latency | 100/100 | ██████████ |
| Turn-taking and interruptions | 100/100 | ██████████ |
| Tools | n/a |  |
| Knowledge base | n/a |  |
| Guardrails and sensitive data | 80/100 | ████████░░ |
| Evaluation and data collection | 83/100 | ████████░░ |
| Call duration and ending | 100/100 | ██████████ |

## Priorities (highest impact first)

1. **Who can start conversations** (medium) — Public agent with no domain allowlist: anyone with the id can open sessions and burn credits. For a web widget, add the customer's domain to the allowlist; for apps, use signed URLs.
2. **Automated tests** (low) — No attached tests or simulations: every prompt change is tested by hand. Save 3-5 hard conversations as tests and run them before each change.

## Detail by dimension

### Prompt structure · 100/100

- ✅ **Role or personality section** — The prompt has an explicit role or personality section.
- ✅ **Goal section** — The prompt has an explicit goal section.
- ✅ **Tone section** — The prompt has an explicit tone section.
- ✅ **Guardrails section** — The prompt has an explicit guardrails section.
- ✅ **Error handling section** — The prompt has an explicit error handling section.
- ✅ **Escalation to a human section** — The prompt has an explicit escalation to a human section.
- ✅ **Prompt length** — Reasonable length (5682 characters).
- ✅ **Voice style: short answers** — The prompt asks for short answers or one question at a time.
- ✅ **No visual formatting in speech** — The prompt rules out lists, emojis or formatting that speech can't render.

### First message · 100/100

- ✅ **First message** — A first message is set.
- ✅ **Greeting length** — Short greeting (137 characters).
- ✅ **Transparency: discloses it is an AI** — The greeting makes clear it is a virtual assistant.
- ✅ **Ends by inviting the user to talk** — The greeting ends with a question.

### Language and voice · 100/100

- ✅ **TTS model supports the language** — 'eleven_flash_v2_5' supports 'es'.
- ✅ **Prompt and agent language** — Prompt and agent share the same language.
- ✅ **Voice native to the agent language** — Voice 'Melody - Ecommerce Voice' fits 'es'.
- ✅ **Voice accent matches the audience region** — Accent 'argentine' consistent with es-AR.
- ✅ **Voice verified for that model** — The voice is verified in that language on that model.
- ✅ **Consistent Rioplatense variant** — Argentine voice and voseo in the text: the agent sounds local end to end.

### Models and latency · 100/100

- ✅ **LLM generation** — Current LLM: 'gpt-6-luna'.
- ✅ **Real-time TTS model** — 'eleven_flash_v2_5' is real-time ready.
- ✅ **Temperature** — Temperature 0.3.

### Turn-taking and interruptions · 100/100

- ✅ **Turn timeout** — 7.0 s, within the recommended range.
- ✅ **Filler message in the agent's language** — Filler enabled and localized.
- ✅ **ASR keywords** — 4 keywords set (brands, products).

### Tools · n/a

- ➖ **Business tools** — No custom tools: fine for an informational agent; for transactional use cases, connect webhooks or MCP.

### Knowledge base · n/a

- ➖ **Knowledge base** — Knowledge is written inside the prompt, in its own section. Fine while short; move it to the knowledge base as it grows.

### Guardrails and sensitive data · 80/100

- ✅ **Platform guardrails** — Focus and prompt-injection protection are on.
- ✅ **Never ask for sensitive data** — The prompt names the sensitive data it must not request.
- ✅ **Conversation retention** — 30-day retention.
- ❌ **Who can start conversations** — Public agent with no domain allowlist: anyone with the id can open sessions and burn credits.  
  → For a web widget, add the customer's domain to the allowlist; for apps, use signed URLs.
- ✅ **Daily conversation cap** — Daily cap: 50.

### Evaluation and data collection · 83/100

- ✅ **Evaluation criteria** — 5 success criteria defined.
- ✅ **Data collection** — 4 structured field(s) per conversation.
- ❌ **Automated tests** — No attached tests or simulations: every prompt change is tested by hand.  
  → Save 3-5 hard conversations as tests and run them before each change.

### Call duration and ending · 100/100

- ✅ **The agent can end the call** — end_call tool enabled.
- ✅ **The prompt says when to close** — The prompt describes how to close the call.
- ✅ **Maximum duration** — 10-minute maximum.
- ✅ **Message when the maximum is reached** — There is a time-limit closing message.
- ✅ **Prolonged silence** — Abandoned calls have a way out.

## Notes

- Audience region assumed: es-AR.

---
*Generated with elevenagents-auditor. The rubric and the rationale for each rule are in the README.*
