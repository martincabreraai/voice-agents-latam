# elevenagents-auditor

A command-line tool that reads the configuration of an **ElevenAgents** voice agent (from the API or an exported JSON) and audits it against a rubric of good practices for voice agents in Spanish. It returns a scored report in Markdown and HTML, in English and Spanish, with findings and concrete fixes.

It runs on one agent, or on a whole workspace at once to show which gaps repeat across many agents.

> Built as a working prototype of a core customer-adoption task: **proactively audit customer agents' prompts, configurations and feature setup, find the gaps, and turn them into recommendations that drive deeper adoption.**

- Read-only: it only calls `GET` endpoints. It never changes an agent.
- No dependencies: Python 3.9+ standard library. Runs anywhere, fast.
- Bilingual: every finding and recommendation exists in Spanish and English.

## Quick start

```bash
# Offline, from an exported config (sample included)
python3 -m elevenagents_auditor audit \
  --file ../agente-rioplatense/config.json \
  --voice ../agente-rioplatense/voz.json \
  --out reports

# Live, from your workspace (GET only)
export ELEVENLABS_API_KEY=...        # never commit it
python3 -m elevenagents_auditor audit --agent-id <AGENT_ID> --out reports

# A whole book of agents, anonymized, with an aggregate summary
python3 -m elevenagents_auditor batch --all --anonymize --out reports/book

# Tests
python3 -m unittest discover -s tests -t . -v
```

Sample output for the demo agent in this repo: [`examples/`](examples/) (`demo-agent.en.md`, `demo-agent.es.md` and HTML versions).

## What it checks: 10 dimensions

Each rule has a severity (critical 5, high 3, medium 2, low 1 points). A dimension's score is the weighted share of rules passed (a partial pass counts half). Rules that don't apply are left out, so an agent without tools isn't penalized for tool hygiene. The overall score is the average of the dimensions that apply.

The score measures **coverage of a configuration checklist**, not conversation quality. Two safeguards keep it honest: a failed **critical** rule (for example, an English-only voice model in a Spanish agent, or a prompt that tells the agent to ask for passwords) sets the verdict to *Blocked* whatever the average says, and anything the auditor can't verify (a model it doesn't know, tools referenced by id) is scored as *not verified* (half credit), never as a pass.

| # | Dimension | What it looks at | Why it matters |
|---|---|---|---|
| 1 | **Prompt structure** | Explicit sections for role, goal, tone, guardrails, error handling and escalation to a human; prompt length; voice-specific style (short turns, one question at a time, no markdown or emojis). | The ElevenLabs prompting guide recommends clean, headed sections: models attend more to titled sections (especially `# Guardrails`) and rules don't bleed into each other. Missing error handling is the main cause of invented answers. On voice, long turns feel like an answering machine. |
| 2 | **First message** | Present, short (≤3 real sentences), discloses it's an AI, ends with a question, same language as the agent, dynamic variables have defaults. | The greeting sets the user's expectations and how fast they get to their use case. Disclosure builds trust and anticipates synthetic-media rules (e.g. the EU AI Act). A greeting without a question leaves people silent. |
| 3 | **Language and voice** | TTS model supports the agent language (English-only models in a Spanish agent is **critical**); prompt and agent in the same language; voice native to the language; voice accent matches the audience region; for Argentina, voseo used consistently; voice verified on that model. | "Spanish" is not one market. An Argentine voice reading neutral *tú* grammar sounds off to locals; a Mexican voice for a Buenos Aires audience costs trust. Regional fit is a LATAM adoption lever. |
| 4 | **Models and latency** | LLM generation (older generations flagged for benchmarking); real-time TTS (Turbo → Flash; `eleven_multilingual_v2` is not built for real time); temperature; reasoning settings; backup LLM not disabled. | Latency is the first thing users feel on a call. The docs recommend Flash over Turbo (same quality, lower latency), low reasoning effort for voice, and never disabling the backup LLM in production. |
| 5 | **Turn-taking and interruptions** | Turn timeout in a sane range; the "wait" filler is in the agent's language (the default filler is in English); ASR keywords for brand and product names. | A 2-second timeout talks over users who are thinking; 20 seconds feels like a dropped call. An English filler in a Spanish call breaks the experience at the worst moment. Brand names mis-transcribed lead to wrong answers. |
| 6 | **Tools** | Each custom tool has a real description, documented parameters, is explained in the prompt, and the prompt says what to do when a tool fails. | The docs are explicit: parameter descriptions act as inline documentation, and agents without error handling hallucinate tool results. |
| 7 | **Knowledge base** | A KB referenced in the prompt but not attached; grounding instruction ("answer only from the KB, otherwise say you don't know"); RAG for larger bases; URL sources that can go stale. | Knowledge drift is silent: the agent keeps answering confidently from outdated or missing documents. |
| 8 | **Guardrails and sensitive data** | Platform guardrails (focus, prompt injection); the prompt forbids requesting passwords, cards, IDs or bank details (a prompt that asks for them is **critical**); retention period; PII redaction that covers the entities actually collected (by field name or description); domain allowlist or auth; a daily cap. | These are the questions a customer's security or legal team will ask before scaling. An agent with no allowlist can be started by anyone who finds its id, burning the customer's credits. |
| 9 | **Evaluation and data collection** | Success criteria (≥2), structured data collection, attached tests or simulations. | Without criteria there is no way to know whether the agent meets its goal, and no leading metric for adoption. The docs recommend tracking task completion and escalation rate and running regression tests before each prompt change. |
| 10 | **Call duration and ending** | `end_call` enabled; the prompt says how to close; sensible max duration; a message when the max is reached; a way out of abandoned (silent) calls. | Calls that can't end themselves waste minutes and end abruptly, which is the last memory the user keeps. |

Heuristics are simple on purpose (keyword and heading detection, a small Spanish/English stopword vote), so they can be fooled; the test suite includes adversarial cases from an independent review. Where it matters, a keyword only counts in the right context: "never ask for the password" passes the sensitive-data rule and "ask for the password" fails it; "no emojis" passes and "use emojis" fails; "never use *tú*" is not counted as using *tú*. When the tool can't verify something (no voice metadata offline, a region inferred only from the voice accent), it says so instead of guessing.

Model guidance was checked against the official ElevenLabs docs on 20 October 2026 (models, prompting guide, guardrails, redaction). Model lineups change often; the lists live in one place at the top of `rules.py`.

## How it fits an adoption program

The task is to audit customer agents' prompts, configurations and feature setup, and to turn that into recommendations that drive deeper adoption. This tool does the first pass in seconds so the human time goes to the conversation with the customer:

1. **Before a QBR or check-in:** run `audit --agent-id` and bring a one-page report with the three highest-impact fixes.
2. **As a self-serve offer:** the same report, sent automatically to new customers in week two of onboarding ("here's how your agent compares to good practice").
3. **As an input to programs:** the batch summary shows which gaps repeat across the book. A gap that 70% of agents share is not fixed account by account. It is fixed with a webinar, a template or an onboarding step.

## Scaling to a high-volume book

`batch --all` already lists every agent in a workspace, audits it and writes:

- `summary.{es,en}.md`: average per dimension, distribution, and the **most frequent gaps** with the % of agents affected;
- `summary.csv`: one row per agent (overall, ten dimension scores, number of gaps by severity), ready for a BI tool;
- one report per agent (two agents with the same name get separate files).

`--anonymize` replaces each agent's name with *Agent 01, 02…* everywhere in the reports, drops agent ids and quoted evidence (such as the greeting). It does not detect other identifiers inside prompts or tool names, such as a client's brand: review the output before sharing it.

For a regional book of hundreds of customers, the same engine would run as a scheduled job over the agents the team is allowed to see, with these additions:

- **Segment and trend.** Join `summary.csv` with account data (segment, plan, region, use case, days since onboarding) owned by RevOps, and track each dimension weekly. The leading indicators are rising audit scores and evaluation criteria turned on. The lagging ones are conversation success rate, minutes per agent, expansion to a second use case and renewal.
- **Trigger plays from rules.** For example, "no evaluation criteria after 14 days" sends a short guide and a webinar invite, and "English-only TTS in a Spanish agent" sends an immediate note.
- **Close the loop with conversations.** Add the conversation analytics the API already exposes (success evaluation, data collection, call length) so the audit says not only "this setting is risky" but "this agent's success rate is 20 points below its peers".
- **Keep humans for judgment.** The auditor ranks and drafts. The strategist decides what to tell each customer and which patterns become a new program.

## Limits

- It audits configuration, not behaviour. A clean config can still have a bad conversation, so pair it with simulations and transcript review.
- Keyword heuristics are tuned for Spanish and English prompts.
- Workspace tools referenced by id are not inspected, offline or via the API: they are flagged as *not verified*.

---

## En español

**Qué es.** Una herramienta de línea de comandos que lee la configuración de un agente de ElevenAgents (por la API o desde un JSON exportado) y la evalúa contra una rúbrica de buenas prácticas para agentes de voz en español. Devuelve un informe con puntaje por dimensión, hallazgos y recomendaciones concretas, en español y en inglés, en Markdown y en HTML. Solo lee: nunca modifica un agente. El puntaje mide cuánto de la lista de buenas prácticas cubre la configuración, no la calidad de las conversaciones; una falla crítica deja el veredicto en *Bloqueado* aunque el promedio sea alto, y lo que no se puede verificar cuenta como *no verificado*, nunca como aprobado.

**Por qué existe.** Una tarea central de adopción es auditar de forma proactiva los prompts, la configuración y el uso de funciones de los agentes de los clientes, detectar brechas y convertirlas en recomendaciones que profundicen el uso. Esto es un prototipo funcionando de esa tarea.

**Las diez dimensiones:** estructura del prompt, primer mensaje, idioma y voz (incluido el acento regional y el voseo), modelos y latencia, turnos e interrupciones, herramientas, base de conocimiento, guardrails y datos sensibles, evaluación y recolección de datos, y duración y cierre de la llamada. El porqué de cada regla está en la tabla de arriba.

**Cómo se usa en el rol.** (1) Antes de una reunión con un cliente, un informe de una página con las tres correcciones de mayor impacto. (2) Como oferta autoservicio, el informe enviado en la segunda semana del onboarding. (3) Como insumo de programas: el resumen de toda la cartera muestra qué brechas se repiten. Una brecha que comparte el 70 % de los agentes no se arregla cuenta por cuenta: se arregla con un webinar, una plantilla o un paso del onboarding.

**Cómo escala.** `batch --all` audita todos los agentes de un workspace y genera un resumen por dimensión, las brechas más frecuentes y un CSV por agente. Con los datos de cuenta de RevOps (segmento, plan, caso de uso, antigüedad) se miden tendencias semanales, se disparan acciones por regla y se cruzan con las métricas de conversación (éxito, duración, expansión, renovación).

## License

MIT. See [LICENSE](../LICENSE).
