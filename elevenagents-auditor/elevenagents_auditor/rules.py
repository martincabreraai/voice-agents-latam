"""The rubric: ten dimensions, each a set of checks over an ElevenAgents config.

Every check returns a RuleResult with a bilingual finding and recommendation.
The "why" behind each rule is documented in README.md (section "The rubric").

Input is the JSON returned by GET /v1/convai/agents/{agent_id} or the body you
would send to POST /v1/convai/agents/create (same shape). Voice metadata
(GET /v1/voices/{voice_id}) is optional; without it, voice-accent checks are
skipped and say so.
"""
import re
from typing import Any, Callable, Dict, List, Optional

from .model import RuleResult, Text, dig
from . import textutil as tu

DIMENSIONS: Dict[str, Text] = {
    "prompt": Text("Estructura del prompt", "Prompt structure"),
    "first_message": Text("Primer mensaje", "First message"),
    "language_voice": Text("Idioma y voz", "Language and voice"),
    "models": Text("Modelos y latencia", "Models and latency"),
    "turns": Text("Turnos e interrupciones", "Turn-taking and interruptions"),
    "tools": Text("Herramientas", "Tools"),
    "knowledge": Text("Base de conocimiento", "Knowledge base"),
    "safety": Text("Guardrails y datos sensibles", "Guardrails and sensitive data"),
    "evaluation": Text("Evaluación y recolección de datos", "Evaluation and data collection"),
    "lifecycle": Text("Duración y cierre de la llamada", "Call duration and ending"),
}

# Model knowledge, checked against the official docs in October 2026
# (elevenlabs.io/docs/overview/models and /eleven-agents/customization/llm).
ENGLISH_ONLY_TTS = {"eleven_flash_v2", "eleven_turbo_v2"}
TURBO_TO_FLASH = {"eleven_turbo_v2_5": "eleven_flash_v2_5", "eleven_turbo_v2": "eleven_flash_v2"}
NON_REALTIME_TTS = {"eleven_multilingual_v2"}
LEGACY_LLM_PREFIXES = ("gpt-3.5", "gpt-4-", "gpt-4o", "gemini-1.5", "gemini-2.0", "claude-3", "grok-beta")
LEGACY_LLM_EXACT = {"gpt-4"}

VOICE_AGENT_STYLE = ["breve", "breves", "corta", "cortas", "conciso", "concise", "short", "brief",
                     "una pregunta", "one question", "una sola", "una o dos oraciones",
                     "one or two sentences"]
NO_MARKDOWN = ["markdown", "emoji", "emojis", "vinetas", "listas", "bullet", "formato", "formatting"]
AI_DISCLOSURE = ["asistente virtual", "agente virtual", "inteligencia artificial", " ia ", "(ia)",
                 "virtual assistant", "ai assistant", "an ai", "artificial intelligence", " bot ",
                 "asistente de ia", "agente de ia"]
SENSITIVE_DATA = ["contrasena", "password", "tarjeta", "card number", "cbu", "cvu", "dni",
                  "codigo de verificacion", "verification code", "datos bancarios", "bank details",
                  "datos sensibles", "sensitive data", "social security", "cuit"]
KB_REFERENCES = ["base de conocimiento", "knowledge base", "documentos adjuntos", "documento adjunto",
                 "attached documents", "segun los documentos", "according to the documents", "faq"]
END_CALL_GUIDANCE = ["end_call", "terminar la llamada", "finalizar la llamada", "cortar", "despedi",
                     "end the call", "hang up", "goodbye", "cierre de la llamada", "cerrar la conversacion"]
PII_FIELD_HINTS = ["email", "mail", "correo", "telefono", "phone", "dni", "documento", "nombre",
                   "name", "address", "direccion", "cuit", "tarjeta", "card"]

Check = Callable[["Ctx"], List[RuleResult]]
CHECKS: List[Check] = []


def check(fn: Check) -> Check:
    CHECKS.append(fn)
    return fn


class Ctx:
    """Everything a check needs, pre-extracted from the raw config."""

    def __init__(self, cfg: Dict[str, Any], voice: Optional[Dict[str, Any]] = None,
                 region: Optional[str] = None):
        self.cfg = cfg
        self.cc = cfg.get("conversation_config") or {}
        self.ps = cfg.get("platform_settings") or {}
        self.agent = self.cc.get("agent") or {}
        self.p = self.agent.get("prompt") or {}
        self.prompt = self.p.get("prompt") or ""
        self.first = self.agent.get("first_message") or ""
        self.lang = (self.agent.get("language") or "en").split("-")[0]
        self.tts = self.cc.get("tts") or {}
        self.turn = self.cc.get("turn") or {}
        self.conv = self.cc.get("conversation") or {}
        self.voice = voice
        self.text_only = bool(self.conv.get("text_only"))
        self.built_in = self.p.get("built_in_tools") or {}
        # Custom (non-system) tools defined inline; tool_ids are workspace tools.
        inline = self.p.get("tools") or []
        self.custom_tools = [t for t in inline if (t or {}).get("type") != "system"]
        self.tool_ids = self.p.get("tool_ids") or []
        self.system_tool_names = {k for k, v in self.built_in.items() if v}
        self.system_tool_names |= {t.get("name") for t in inline if (t or {}).get("type") == "system"}
        self.kb = self.p.get("knowledge_base") or []
        self.region = region or self._infer_region()

    def _infer_region(self) -> Optional[str]:
        if self.voice:
            accent = tu.normalize(str(dig(self.voice, "labels.accent", "")))
            if "argentin" in accent or "rioplatense" in accent:
                return "es-AR"
            if "mexic" in accent:
                return "es-MX"
        if self.lang == "es" and tu.uses_voseo(self.prompt):
            return "es-AR"
        return None


def R(rule_id, dim, sev, status, title, finding, rec=None, evidence=""):
    return RuleResult(rule_id, dim, sev, status, title, finding, rec, evidence)


# ---------------------------------------------------------------- 1. Prompt
SECTION_LABELS = {
    "role": Text("rol o personalidad", "role or personality"),
    "goal": Text("objetivo", "goal"),
    "tone": Text("tono", "tone"),
    "guardrails": Text("límites (guardrails)", "guardrails"),
    "errors": Text("manejo de errores", "error handling"),
    "escalation": Text("derivación a una persona", "escalation to a human"),
}
SECTION_SEVERITY = {"role": "high", "goal": "high", "tone": "medium", "guardrails": "high",
                    "errors": "medium", "escalation": "medium"}


@check
def prompt_sections(c: Ctx) -> List[RuleResult]:
    out = []
    for key, label in SECTION_LABELS.items():
        status = tu.section_status(c.prompt, key)
        if key == "escalation" and status == "fail" and "transfer_to_number" in c.system_tool_names:
            status = "partial"
        title = Text(f"Sección de {label.es}", f"{label.en.capitalize()} section")
        if status == "pass":
            out.append(R(f"prompt.{key}", "prompt", SECTION_SEVERITY[key], "pass", title,
                         Text(f"El prompt tiene una sección explícita de {label.es}.",
                              f"The prompt has an explicit {label.en} section.")))
        elif status == "partial":
            out.append(R(f"prompt.{key}", "prompt", SECTION_SEVERITY[key], "partial", title,
                         Text(f"Hay instrucciones de {label.es}, pero sueltas en el texto.",
                              f"There are {label.en} instructions, but scattered in the text."),
                         Text(f"Agrupalas bajo un encabezado propio (por ejemplo, '# {label.es.capitalize()}'): "
                              "los modelos les prestan más atención a las secciones con título y el prompt se audita más fácil.",
                              f"Group them under their own heading (for example '# {label.en.capitalize()}'): models "
                              "attend more to titled sections and the prompt becomes easier to audit.")))
        else:
            out.append(R(f"prompt.{key}", "prompt", SECTION_SEVERITY[key], "fail", title,
                         Text(f"No encontré instrucciones de {label.es}.",
                              f"No {label.en} instructions found."),
                         Text(_section_fix_es(key), _section_fix_en(key))))
    return out


def _section_fix_es(key: str) -> str:
    return {
        "role": "Agregá '# Personalidad': quién es el agente, para quién trabaja y que es una IA.",
        "goal": "Agregá '# Objetivo' con el resultado que define una llamada exitosa y los pasos para llegar.",
        "tone": "Agregá '# Tono': registro, largo de las respuestas y variante del idioma.",
        "guardrails": "Agregá '# Límites': de qué no habla, qué no promete y qué datos nunca pide.",
        "errors": "Agregá '# Manejo de errores': qué hacer si no entiende, si no sabe o si falla una herramienta. "
                  "Sin esto, el modelo tiende a inventar.",
        "escalation": "Agregá '# Derivación': cuándo y cómo pasar a una persona (motivos, canal, horario).",
    }[key]


def _section_fix_en(key: str) -> str:
    return {
        "role": "Add '# Personality': who the agent is, who it works for, and that it is an AI.",
        "goal": "Add '# Goal' with the outcome that defines a successful call and the steps to get there.",
        "tone": "Add '# Tone': register, answer length and language variant.",
        "guardrails": "Add '# Guardrails': topics to avoid, promises it must not make and data it must never ask for.",
        "errors": "Add '# Error handling': what to do when it doesn't understand, doesn't know, or a tool fails. "
                  "Without it, models tend to make things up.",
        "escalation": "Add '# Escalation': when and how to hand off to a human (triggers, channel, hours).",
    }[key]


@check
def prompt_length(c: Ctx) -> List[RuleResult]:
    n = len(c.prompt)
    title = Text("Largo del prompt", "Prompt length")
    if n < 400:
        return [R("prompt.length", "prompt", "high", "fail", title,
                  Text(f"El prompt tiene {n} caracteres: demasiado corto para un agente en producción.",
                       f"The prompt has {n} characters: too thin for a production agent."),
                  Text("Desarrollá objetivo, límites y manejo de errores; un prompt mínimo deja al modelo improvisando.",
                       "Flesh out goal, guardrails and error handling; a minimal prompt leaves the model improvising."),
                  f"{n} chars")]
    if n > 15000:
        return [R("prompt.length", "prompt", "medium", "partial", title,
                  Text(f"El prompt tiene {n} caracteres: mucho contexto fijo en cada turno.",
                       f"The prompt has {n} characters: a lot of fixed context on every turn."),
                  Text("Pasá el contenido de referencia a la base de conocimiento (con RAG) o a procedimientos; "
                       "dejá en el prompt solo comportamiento.",
                       "Move reference content to the knowledge base (with RAG) or to procedures; keep only "
                       "behaviour in the prompt."), f"{n} chars")]
    return [R("prompt.length", "prompt", "high", "pass", title,
              Text(f"Largo razonable ({n} caracteres).", f"Reasonable length ({n} characters)."), evidence=f"{n} chars")]


@check
def prompt_voice_style(c: Ctx) -> List[RuleResult]:
    if c.text_only:
        return []
    out = []
    title = Text("Estilo para voz: respuestas cortas", "Voice style: short answers")
    if tu.contains_any(c.prompt, VOICE_AGENT_STYLE):
        out.append(R("prompt.voice_brevity", "prompt", "medium", "pass", title,
                     Text("El prompt pide respuestas cortas o una pregunta por vez.",
                          "The prompt asks for short answers or one question at a time.")))
    else:
        out.append(R("prompt.voice_brevity", "prompt", "medium", "fail", title,
                     Text("El prompt no pide brevedad. En voz, las respuestas largas se sienten como un contestador.",
                          "The prompt doesn't ask for brevity. On voice, long answers feel like an answering machine."),
                     Text("Agregá en '# Tono': 'una o dos oraciones por turno y una sola pregunta por vez'.",
                          "Add to '# Tone': 'one or two sentences per turn and a single question at a time'.")))
    title = Text("Sin formato visual en la voz", "No visual formatting in speech")
    if tu.contains_any(c.prompt, NO_MARKDOWN):
        out.append(R("prompt.no_markdown", "prompt", "low", "pass", title,
                     Text("El prompt evita listas, emojis o formato que la voz no puede leer.",
                          "The prompt rules out lists, emojis or formatting that speech can't render.")))
    else:
        out.append(R("prompt.no_markdown", "prompt", "low", "fail", title,
                     Text("No se le dice al modelo que evite listas, emojis o markdown.",
                          "The model isn't told to avoid lists, emojis or markdown."),
                     Text("Agregá: 'nada de listas, viñetas ni emojis: todo lo que escribís se convierte en voz'.",
                          "Add: 'no lists, bullets or emojis: everything you write is spoken aloud'.")))
    return out


# --------------------------------------------------------- 2. First message
@check
def first_message(c: Ctx) -> List[RuleResult]:
    dim = "first_message"
    out = []
    fm = c.first.strip()
    if not fm:
        return [R("first.present", dim, "high", "fail", Text("Primer mensaje", "First message"),
                  Text("No hay primer mensaje: el agente espera en silencio a que hable el usuario.",
                       "No first message: the agent waits silently for the user to speak."),
                  Text("Salvo en llamadas salientes donde atiende una persona, definí un saludo que diga quién habla "
                       "y para qué sirve la llamada.",
                       "Unless it's an outbound call answered by a person, set a greeting that says who is "
                       "speaking and what the call is for."))]
    out.append(R("first.present", dim, "high", "pass", Text("Primer mensaje", "First message"),
                 Text("Hay primer mensaje.", "A first message is set."), evidence=fm[:160]))
    n, s = len(fm), tu.sentence_count(fm)
    title = Text("Largo del saludo", "Greeting length")
    if n > 240 or s > 3:
        out.append(R("first.length", dim, "medium", "fail", title,
                     Text(f"El saludo tiene {n} caracteres y {s} oraciones: el usuario tarda en poder hablar.",
                          f"The greeting is {n} characters and {s} sentences: the user waits too long to talk."),
                     Text("Bajalo a dos o tres oraciones cortas: quién sos, para qué, y una pregunta.",
                          "Cut it to two or three short sentences: who you are, what for, and one question.")))
    else:
        out.append(R("first.length", dim, "medium", "pass", title,
                     Text(f"Saludo breve ({n} caracteres).", f"Short greeting ({n} characters).")))
    title = Text("Transparencia: se presenta como IA", "Transparency: discloses it is an AI")
    if tu.contains_any(" " + fm + " ", AI_DISCLOSURE):
        out.append(R("first.ai_disclosure", dim, "medium", "pass", title,
                     Text("El saludo deja claro que es un asistente virtual.",
                          "The greeting makes clear it is a virtual assistant.")))
    else:
        out.append(R("first.ai_disclosure", dim, "medium", "fail", title,
                     Text("El saludo no dice que es una IA o un asistente virtual.",
                          "The greeting doesn't say it is an AI or a virtual assistant."),
                     Text("Agregá 'asistente virtual' en el saludo: genera confianza y anticipa exigencias "
                          "regulatorias sobre contenido sintético (por ejemplo, la AI Act de la UE).",
                          "Add 'virtual assistant' to the greeting: it builds trust and anticipates synthetic-media "
                          "disclosure rules (for example the EU AI Act).")))
    title = Text("Termina invitando a hablar", "Ends by inviting the user to talk")
    if fm.rstrip().endswith("?") or "¿" in fm:
        out.append(R("first.invites", dim, "low", "pass", title,
                     Text("El saludo cierra con una pregunta.", "The greeting ends with a question.")))
    else:
        out.append(R("first.invites", dim, "low", "fail", title,
                     Text("El saludo no termina en una pregunta: el usuario no sabe qué decir.",
                          "The greeting doesn't end with a question: the user doesn't know what to say."),
                     Text("Cerrá con una pregunta concreta que lleve al caso de uso principal.",
                          "End with a concrete question that leads into the core use case.")))
    detected = tu.detect_language(fm)
    if detected and detected != c.lang:
        out.append(R("first.language", dim, "high", "fail", Text("Idioma del saludo", "Greeting language"),
                     Text(f"El saludo parece estar en '{detected}' y el agente está configurado en '{c.lang}'.",
                          f"The greeting looks like '{detected}' while the agent language is '{c.lang}'."),
                     Text("Alineá el idioma del saludo con el del agente (o usá presets por idioma).",
                          "Align the greeting language with the agent language (or use language presets).")))
    variables = re.findall(r"{{\s*([\w.]+)\s*}}", fm)
    if variables:
        placeholders = dig(c.agent, "dynamic_variables.dynamic_variable_placeholders", {}) or {}
        missing = [v for v in variables if v not in placeholders and not v.startswith("system__")]
        title = Text("Variables dinámicas del saludo", "Greeting dynamic variables")
        if missing:
            out.append(R("first.variables", dim, "medium", "fail", title,
                         Text(f"El saludo usa variables sin valor por defecto: {', '.join(missing)}.",
                              f"The greeting uses variables with no default value: {', '.join(missing)}."),
                         Text("Definí valores por defecto para que el saludo no se rompa si el dato no llega.",
                              "Set default values so the greeting doesn't break when the value is missing.")))
        else:
            out.append(R("first.variables", dim, "medium", "pass", title,
                         Text("Las variables del saludo tienen valor por defecto.",
                              "Greeting variables have defaults.")))
    return out


# ------------------------------------------------------- 3. Language & voice
@check
def language_and_voice(c: Ctx) -> List[RuleResult]:
    dim = "language_voice"
    out = []
    model = c.tts.get("model_id") or ""
    title = Text("Modelo de voz compatible con el idioma", "TTS model supports the language")
    if c.lang != "en" and model in ENGLISH_ONLY_TTS:
        out.append(R("lang.tts_language", dim, "critical", "fail", title,
                     Text(f"El agente habla '{c.lang}' pero el modelo de voz '{model}' es solo inglés.",
                          f"The agent speaks '{c.lang}' but TTS model '{model}' is English-only."),
                     Text("Usá eleven_flash_v2_5 (multilingüe, ~75 ms) o eleven_v3_conversational.",
                          "Use eleven_flash_v2_5 (multilingual, ~75 ms) or eleven_v3_conversational."),
                     model))
    elif model:
        out.append(R("lang.tts_language", dim, "critical", "pass", title,
                     Text(f"'{model}' soporta '{c.lang}'.", f"'{model}' supports '{c.lang}'."), evidence=model))
    detected = tu.detect_language(c.prompt)
    title = Text("Idioma del prompt y del agente", "Prompt and agent language")
    if detected and detected != c.lang:
        out.append(R("lang.prompt_language", dim, "medium", "partial", title,
                     Text(f"El prompt está en '{detected}' y el agente en '{c.lang}'.",
                          f"The prompt is written in '{detected}' and the agent is set to '{c.lang}'."),
                     Text("Funciona, pero los ejemplos y frases modelo del prompt se filtran a las respuestas: "
                          "escribí el prompt (o al menos los ejemplos) en el idioma del usuario.",
                          "It works, but example phrases leak into answers: write the prompt (or at least its "
                          "examples) in the user's language.")))
    elif detected:
        out.append(R("lang.prompt_language", dim, "medium", "pass", title,
                     Text("Prompt y agente en el mismo idioma.", "Prompt and agent share the same language.")))
    if c.voice:
        out += _voice_checks(c, dim, model)
    else:
        out.append(R("lang.voice_accent", dim, "medium", "na",
                     Text("Acento de la voz", "Voice accent"),
                     Text("Sin datos de la voz: corré con --agent-id (o pasá --voice) para verificar acento e idioma.",
                          "No voice metadata: run with --agent-id (or pass --voice) to check accent and language.")))
    if c.lang == "es" and c.region == "es-AR":
        title = Text("Variante rioplatense coherente", "Consistent Rioplatense variant")
        voseo, tuteo = tu.uses_voseo(c.prompt + "\n" + c.first), tu.uses_tuteo(c.prompt + "\n" + c.first)
        if voseo and not tuteo:
            out.append(R("lang.voseo", dim, "medium", "pass", title,
                         Text("Voz argentina y textos con voseo: el agente suena local de punta a punta.",
                              "Argentine voice and voseo in the text: the agent sounds local end to end.")))
        elif tuteo:
            out.append(R("lang.voseo", dim, "medium", "fail", title,
                         Text("La voz o la región es argentina, pero el prompt o el saludo usan tuteo "
                              "('eres', 'puedes'): acento rioplatense con gramática neutra suena raro.",
                              "The voice or region is Argentine, but the prompt or greeting use 'tú' forms: "
                              "an Argentine accent with neutral grammar sounds off to local users."),
                         Text("Pedí voseo explícito en '# Tono' y reescribí el saludo con 'vos'.",
                              "Ask for voseo explicitly under '# Tone' and rewrite the greeting with 'vos'.")))
        else:
            out.append(R("lang.voseo", dim, "medium", "partial", title,
                         Text("La voz es argentina, pero el prompt no pide voseo: el modelo tiende a un español neutro.",
                              "The voice is Argentine, but the prompt doesn't ask for voseo: the model drifts to "
                              "neutral Spanish."),
                         Text("Agregá en '# Tono': 'español rioplatense, con voseo; nunca uses tú'.",
                              "Add under '# Tone': 'Rioplatense Spanish with voseo; never use tú'.")))
    return out


def _voice_checks(c: Ctx, dim: str, model: str) -> List[RuleResult]:
    out = []
    labels = c.voice.get("labels") or {}
    accent = tu.normalize(str(labels.get("accent") or ""))
    vlang = tu.normalize(str(labels.get("language") or ""))
    verified = c.voice.get("verified_languages") or []
    verified_langs = {(v.get("language") or "").split("-")[0] for v in verified}
    title = Text("Voz nativa del idioma del agente", "Voice native to the agent language")
    native = vlang.startswith(c.lang) or c.lang in verified_langs
    if not native and c.voice.get("category") not in ("cloned", "generated"):
        out.append(R("lang.voice_native", dim, "high", "fail", title,
                     Text(f"La voz '{c.voice.get('name')}' no figura como voz de '{c.lang}' (acento: {accent or 's/d'}).",
                          f"Voice '{c.voice.get('name')}' is not listed for '{c.lang}' (accent: {accent or 'n/a'})."),
                     Text("Elegí en la Voice Library una voz verificada para el idioma y la región del público.",
                          "Pick a Voice Library voice verified for the audience's language and region.")))
    else:
        out.append(R("lang.voice_native", dim, "high", "pass", title,
                     Text(f"Voz '{c.voice.get('name')}' apta para '{c.lang}'.",
                          f"Voice '{c.voice.get('name')}' fits '{c.lang}'.")))
    if c.region:
        want = {"es-AR": "argentin", "es-MX": "mexic"}.get(c.region)
        title = Text("Acento de la voz y región del público", "Voice accent matches the audience region")
        if want and want in accent:
            out.append(R("lang.voice_accent", dim, "medium", "pass", title,
                         Text(f"Acento '{labels.get('accent')}' coherente con {c.region}.",
                              f"Accent '{labels.get('accent')}' consistent with {c.region}.")))
        elif want:
            out.append(R("lang.voice_accent", dim, "medium", "fail", title,
                         Text(f"El público es {c.region} y la voz tiene acento '{labels.get('accent') or 's/d'}'.",
                              f"The audience is {c.region} and the voice accent is '{labels.get('accent') or 'n/a'}'."),
                         Text("Probá dos o tres voces del acento regional con el mismo guion y elegí con usuarios reales.",
                              "Test two or three regional-accent voices on the same script and pick with real users.")))
    if model and verified:
        ok = any(v.get("model_id") == model and (v.get("language") or "").startswith(c.lang) for v in verified)
        title = Text("Voz verificada para ese modelo", "Voice verified for that model")
        out.append(R("lang.voice_model", dim, "low", "pass" if ok else "partial", title,
                     Text("La voz está verificada en ese idioma con ese modelo." if ok else
                          f"La voz no figura verificada en '{c.lang}' con '{model}'.",
                          "The voice is verified in that language on that model." if ok else
                          f"The voice is not listed as verified in '{c.lang}' on '{model}'."),
                     None if ok else Text("Escuchá una muestra en ese modelo antes de producción.",
                                          "Listen to a sample on that model before going live.")))
    return out


# ------------------------------------------------------- 4. Models & latency
@check
def models_latency(c: Ctx) -> List[RuleResult]:
    dim = "models"
    out = []
    llm = c.p.get("llm") or ""
    title = Text("Generación del LLM", "LLM generation")
    legacy = llm in LEGACY_LLM_EXACT or llm.startswith(LEGACY_LLM_PREFIXES)
    if legacy:
        out.append(R("models.llm_generation", dim, "medium", "fail", title,
                     Text(f"El LLM '{llm}' es de una generación anterior a la que hoy recomienda la documentación.",
                          f"LLM '{llm}' is older than what the docs currently recommend."),
                     Text("Probá dos o tres candidatos actuales de baja latencia con tus propios casos y medí latencia, "
                          "aciertos y llamadas a herramientas antes de cambiar.",
                          "Benchmark two or three current low-latency candidates on your own cases (latency, accuracy, "
                          "tool calls) before switching."), llm))
    elif llm:
        out.append(R("models.llm_generation", dim, "medium", "pass", title,
                     Text(f"LLM actual: '{llm}'.", f"Current LLM: '{llm}'."), evidence=llm))
    model = c.tts.get("model_id") or ""
    title = Text("Modelo de voz para tiempo real", "Real-time TTS model")
    if model in TURBO_TO_FLASH:
        out.append(R("models.tts_realtime", dim, "low", "partial", title,
                     Text(f"'{model}' funciona, pero la documentación recomienda Flash sobre Turbo (misma calidad, menos latencia).",
                          f"'{model}' works, but the docs recommend Flash over Turbo (same quality, lower latency)."),
                     Text(f"Cambiá a '{TURBO_TO_FLASH[model]}'.", f"Switch to '{TURBO_TO_FLASH[model]}'."), model))
    elif model in NON_REALTIME_TTS:
        out.append(R("models.tts_realtime", dim, "medium", "fail", title,
                     Text(f"'{model}' es un modelo de alta calidad pero no está pensado para tiempo real: suma latencia en cada turno.",
                          f"'{model}' is a high-quality model not designed for real time: it adds latency to every turn."),
                     Text("Usá eleven_flash_v2_5 (~75 ms) o, si importa la expresividad, eleven_v3_conversational.",
                          "Use eleven_flash_v2_5 (~75 ms) or, if expressiveness matters, eleven_v3_conversational."), model))
    elif model:
        out.append(R("models.tts_realtime", dim, "medium", "pass", title,
                     Text(f"'{model}' es apto para tiempo real.", f"'{model}' is real-time ready."), evidence=model))
    temp = c.p.get("temperature")
    if isinstance(temp, (int, float)):
        title = Text("Temperatura", "Temperature")
        if temp > 0.7:
            out.append(R("models.temperature", dim, "low", "fail", title,
                         Text(f"Temperatura {temp}: alta para un agente con pasos y políticas.",
                              f"Temperature {temp}: high for an agent with steps and policies."),
                         Text("Para soporte u onboarding, 0 a 0,4 da respuestas más consistentes.",
                              "For support or onboarding, 0 to 0.4 gives more consistent answers.")))
        else:
            out.append(R("models.temperature", dim, "low", "pass", title,
                         Text(f"Temperatura {temp}.", f"Temperature {temp}.")))
    budget = c.p.get("thinking_budget") or 0
    effort = (c.p.get("reasoning_effort") or "").lower()
    if (isinstance(budget, (int, float)) and budget > 0) or effort in ("medium", "high"):
        out.append(R("models.reasoning", dim, "low", "partial", Text("Razonamiento y latencia", "Reasoning and latency"),
                     Text("Hay razonamiento activado: mejora decisiones pero demora el turno.",
                          "Reasoning is on: better decisions, slower turns."),
                     Text("En voz, empezá con razonamiento bajo y subilo solo en los pasos que lo necesitan.",
                          "On voice, start low and raise reasoning only on steps that need it.")))
    if dig(c.p, "backup_llm_config.preference") == "disabled":
        out.append(R("models.backup", dim, "medium", "fail", Text("LLM de respaldo", "Backup LLM"),
                     Text("El LLM de respaldo está desactivado: si el proveedor falla, la llamada falla.",
                          "Backup LLM is disabled: if the provider fails, the call fails."),
                     Text("Activá el respaldo por defecto; la documentación desaconseja apagarlo en producción.",
                          "Enable the default backup; the docs advise against disabling it in production.")))
    return out


# --------------------------------------------------------------- 5. Turns
@check
def turns(c: Ctx) -> List[RuleResult]:
    if c.text_only:
        return []
    dim = "turns"
    out = []
    tt = c.turn.get("turn_timeout")
    if isinstance(tt, (int, float)):
        title = Text("Espera antes de retomar la palabra", "Turn timeout")
        if tt < 3:
            out.append(R("turns.timeout", dim, "medium", "fail", title,
                         Text(f"{tt} s: el agente retoma demasiado rápido y pisa al usuario que piensa.",
                              f"{tt} s: the agent jumps back in too fast and talks over users who are thinking."),
                         Text("Usá entre 5 y 10 segundos para conversaciones de ayuda.",
                              "Use 5 to 10 seconds for assistance conversations.")))
        elif tt > 15:
            out.append(R("turns.timeout", dim, "low", "fail", title,
                         Text(f"{tt} s: silencios largos que parecen una llamada caída.",
                              f"{tt} s: long silences that feel like a dropped call."),
                         Text("Bajalo a 7 a 10 segundos.", "Lower it to 7-10 seconds.")))
        else:
            out.append(R("turns.timeout", dim, "medium", "pass", title,
                         Text(f"{tt} s, dentro del rango recomendado.", f"{tt} s, within the recommended range.")))
    st = dig(c.turn, "soft_timeout_config.timeout_seconds", -1)
    msg = dig(c.turn, "soft_timeout_config.message", "")
    title = Text("Muletilla de espera en el idioma del agente", "Filler message in the agent's language")
    if isinstance(st, (int, float)) and st > 0:
        english = tu.detect_language(msg) == "en" or tu.contains_any(msg, ["give me", "one moment", "yeah", "hold on", "let me"])
        if c.lang != "en" and msg and english:
            out.append(R("turns.soft_timeout_language", dim, "medium", "fail", title,
                         Text(f"La muletilla de espera está en inglés ('{msg}') y el agente habla '{c.lang}'.",
                              f"The filler is in English ('{msg}') while the agent speaks '{c.lang}'."),
                         Text("Traducila ('Dame un segundito…') o activá la muletilla generada por el LLM.",
                              "Translate it or enable the LLM-generated filler.")))
        else:
            out.append(R("turns.soft_timeout_language", dim, "medium", "pass", title,
                         Text("Muletilla de espera activa y localizada.", "Filler enabled and localized.")))
    elif c.custom_tools or c.tool_ids:
        out.append(R("turns.soft_timeout_language", dim, "low", "fail", title,
                     Text("El agente llama herramientas pero no tiene muletilla de espera: habrá silencios mientras espera.",
                          "The agent calls tools but has no filler: users will hear silence while it waits."),
                     Text("Activá el soft timeout con una frase corta en el idioma del agente.",
                          "Enable the soft timeout with a short phrase in the agent's language.")))
    keywords = dig(c.cc, "asr.keywords", []) or []
    title = Text("Palabras clave para el reconocimiento de voz", "ASR keywords")
    if keywords:
        out.append(R("turns.asr_keywords", dim, "low", "pass", title,
                     Text(f"{len(keywords)} palabras clave cargadas (marcas, productos).",
                          f"{len(keywords)} keywords set (brands, products).")))
    else:
        out.append(R("turns.asr_keywords", dim, "low", "fail", title,
                     Text("Sin palabras clave: nombres de marca o de producto se transcriben mal y el agente responde otra cosa.",
                          "No keywords: brand and product names get mis-transcribed and the agent answers the wrong thing."),
                     Text("Cargá en ASR las marcas, productos y siglas que el usuario va a decir.",
                          "Add the brands, products and acronyms users will say as ASR keywords.")))
    return out


# --------------------------------------------------------------- 6. Tools
@check
def tools(c: Ctx) -> List[RuleResult]:
    dim = "tools"
    out = []
    if not c.custom_tools and not c.tool_ids:
        return [R("tools.none", dim, "low", "na", Text("Herramientas de negocio", "Business tools"),
                  Text("Sin herramientas propias: está bien para un agente informativo; para casos transaccionales, "
                       "conectá webhooks o MCP.",
                       "No custom tools: fine for an informational agent; for transactional use cases, connect "
                       "webhooks or MCP."))]
    for t in c.custom_tools:
        name = t.get("name") or "?"
        desc = t.get("description") or ""
        title = Text(f"Descripción de '{name}'", f"'{name}' description")
        if len(desc) < 30:
            out.append(R(f"tools.description.{name}", dim, "high", "fail", title,
                         Text(f"'{name}' tiene una descripción vacía o muy corta: el modelo no sabe cuándo usarla.",
                              f"'{name}' has an empty or very short description: the model can't tell when to use it."),
                         Text("Describí qué hace, qué devuelve y cuándo usarla, en una o dos oraciones.",
                              "Describe what it does, what it returns and when to use it, in one or two sentences.")))
        else:
            out.append(R(f"tools.description.{name}", dim, "high", "pass", title,
                         Text(f"'{name}' está descripta.", f"'{name}' is described.")))
        params = _tool_params(t)
        undocumented = [p for p, spec in params.items() if not (spec or {}).get("description")]
        if params:
            title = Text(f"Parámetros de '{name}'", f"'{name}' parameters")
            if undocumented:
                out.append(R(f"tools.params.{name}", dim, "medium", "fail", title,
                             Text(f"Parámetros sin descripción: {', '.join(undocumented)}.",
                                  f"Parameters without description: {', '.join(undocumented)}."),
                             Text("Documentá formato y ejemplo de cada parámetro (por ejemplo, 'DNI sin puntos, 8 dígitos').",
                                  "Document each parameter's format with an example.")))
            else:
                out.append(R(f"tools.params.{name}", dim, "medium", "pass", title,
                             Text("Todos los parámetros tienen descripción.", "All parameters are described.")))
        title = Text(f"El prompt explica cuándo usar '{name}'", f"Prompt explains when to use '{name}'")
        if name != "?" and name in c.prompt:
            out.append(R(f"tools.in_prompt.{name}", dim, "medium", "pass", title,
                         Text(f"El prompt menciona '{name}'.", f"The prompt mentions '{name}'.")))
        else:
            out.append(R(f"tools.in_prompt.{name}", dim, "medium", "fail", title,
                         Text(f"El prompt no menciona '{name}'.", f"The prompt never mentions '{name}'."),
                         Text("Agregá una sección '# Herramientas' con cuándo usarla, cómo y qué hacer si falla.",
                              "Add a '# Tools' section with when to use it, how, and what to do if it fails.")))
    if c.tool_ids and not c.custom_tools:
        out.append(R("tools.workspace", dim, "low", "na", Text("Herramientas del workspace", "Workspace tools"),
                     Text(f"{len(c.tool_ids)} herramienta(s) referenciadas por id: su definición no viene en esta configuración.",
                          f"{len(c.tool_ids)} tool(s) referenced by id: their definitions are not in this config.")))
    title = Text("Qué hacer si una herramienta falla", "What to do when a tool fails")
    if tu.contains_any(c.prompt, ["falla", "fails", "error", "no responde", "timeout", "no funciona"]):
        out.append(R("tools.error_handling", dim, "medium", "pass", title,
                     Text("El prompt cubre fallas de herramientas.", "The prompt covers tool failures.")))
    else:
        out.append(R("tools.error_handling", dim, "medium", "fail", title,
                     Text("El prompt no dice qué hacer si una herramienta falla: el modelo puede inventar el resultado.",
                          "The prompt doesn't say what to do when a tool fails: the model may invent the result."),
                     Text("Agregá: 'si la herramienta falla, decilo sin tecnicismos, reintentá una vez y ofrecé derivar'.",
                          "Add: 'if the tool fails, say so plainly, retry once and offer a handoff'.")))
    return out


def _tool_params(tool: Dict[str, Any]) -> Dict[str, Any]:
    params: Dict[str, Any] = {}
    for path in ("api_schema.request_body_schema.properties", "api_schema.query_params_schema.properties",
                 "parameters.properties"):
        params.update(dig(tool, path, {}) or {})
    for p in dig(tool, "api_schema.path_params_schema", {}) or {}:
        params[p] = (dig(tool, "api_schema.path_params_schema", {}) or {}).get(p)
    return params


# ------------------------------------------------------ 7. Knowledge base
@check
def knowledge(c: Ctx) -> List[RuleResult]:
    dim = "knowledge"
    refers = tu.contains_any(c.prompt, KB_REFERENCES)
    if not c.kb:
        inline = any(any(k in h for k in ("knowledge", "conocimiento", "faq", "datos clave"))
                     for h in tu.headings(c.prompt))
        if inline:
            return [R("kb.inline", dim, "low", "na", Text("Base de conocimiento", "Knowledge base"),
                      Text("El conocimiento está escrito dentro del prompt, en su propia sección. Bien mientras sea corto; "
                           "si crece, pasalo a la base de conocimiento.",
                           "Knowledge is written inside the prompt, in its own section. Fine while short; move it to "
                           "the knowledge base as it grows."))]
        if refers:
            return [R("kb.missing", dim, "high", "fail", Text("Base de conocimiento", "Knowledge base"),
                      Text("El prompt menciona documentos o una base de conocimiento, pero no hay ninguna conectada.",
                           "The prompt refers to documents or a knowledge base, but none is attached."),
                      Text("Conectá los documentos o sacá la referencia: si no, el modelo improvisa respuestas.",
                           "Attach the documents or remove the reference; otherwise the model improvises."))]
        return [R("kb.none", dim, "low", "na", Text("Base de conocimiento", "Knowledge base"),
                  Text("Sin base de conocimiento; el conocimiento vive en el prompt. Bien si es corto.",
                       "No knowledge base; knowledge lives in the prompt. Fine if it is short."))]
    out = [R("kb.present", dim, "high", "pass", Text("Base de conocimiento", "Knowledge base"),
             Text(f"{len(c.kb)} documento(s) conectado(s).", f"{len(c.kb)} document(s) attached."))]
    title = Text("Instrucción de no inventar fuera de la base", "Instruction not to answer beyond the KB")
    if tu.section_status(c.prompt, "errors") != "fail":
        out.append(R("kb.grounding", dim, "medium", "pass", title,
                     Text("El prompt dice qué hacer cuando la respuesta no está en la base.",
                          "The prompt says what to do when the answer isn't in the KB.")))
    else:
        out.append(R("kb.grounding", dim, "medium", "fail", title,
                     Text("El prompt no limita las respuestas a la base ni dice qué hacer si el dato no está.",
                          "The prompt doesn't ground answers in the KB or say what to do if the fact is missing."),
                     Text("Agregá: 'respondé solo con la base; si no está, decí que no lo sabés y derivá'.",
                          "Add: 'answer only from the KB; if it isn't there, say you don't know and hand off'.")))
    rag = bool(dig(c.p, "rag.enabled", False))
    title = Text("RAG para bases grandes", "RAG for larger knowledge bases")
    if len(c.kb) >= 3 and not rag:
        out.append(R("kb.rag", dim, "low", "fail", title,
                     Text(f"{len(c.kb)} documentos sin RAG: todo el contenido entra al contexto en cada turno.",
                          f"{len(c.kb)} documents without RAG: all content goes into context every turn."),
                     Text("Activá RAG: baja latencia y costo y mejora la precisión con bases grandes.",
                          "Enable RAG: lower latency and cost, better precision on larger bases.")))
    else:
        out.append(R("kb.rag", dim, "low", "pass", title,
                     Text("Tamaño de base y RAG coherentes.", "KB size and RAG setting are consistent.")))
    urls = [d for d in c.kb if (d or {}).get("type") == "url"]
    if urls:
        out.append(R("kb.freshness", dim, "low", "partial", Text("Vigencia de las URLs", "URL freshness"),
                     Text(f"{len(urls)} documento(s) cargado(s) desde una URL: pueden quedar desactualizados.",
                          f"{len(urls)} document(s) loaded from a URL: they can go stale."),
                     Text("Asigná un responsable y una frecuencia de actualización (o sincronización automática si aplica).",
                          "Assign an owner and a refresh cadence (or auto-sync where available).")))
    return out


# ------------------------------------------------- 8. Guardrails & privacy
@check
def safety(c: Ctx) -> List[RuleResult]:
    dim = "safety"
    out = []
    g = c.ps.get("guardrails") or {}
    on = [k for k in ("focus", "prompt_injection") if dig(g, f"{k}.is_enabled", False)]
    title = Text("Guardrails de la plataforma", "Platform guardrails")
    if len(on) == 2:
        out.append(R("safety.platform_guardrails", dim, "medium", "pass", title,
                     Text("Foco y protección contra prompt injection activados.",
                          "Focus and prompt-injection protection are on.")))
    else:
        missing = [k for k in ("focus", "prompt_injection") if k not in on]
        out.append(R("safety.platform_guardrails", dim, "medium", "partial" if on else "fail", title,
                     Text(f"Guardrails de plataforma apagados: {', '.join(missing)}.",
                          f"Platform guardrails off: {', '.join(missing)}."),
                     Text("Activá 'focus' (mantiene el tema) y 'prompt_injection' (resiste intentos de cambiarle las "
                          "instrucciones); son capas adicionales al prompt.",
                          "Turn on 'focus' (keeps it on topic) and 'prompt_injection' (resists instruction "
                          "hijacking); they add a layer on top of the prompt.")))
    title = Text("Nunca pedir datos sensibles", "Never ask for sensitive data")
    if tu.contains_any(c.prompt, SENSITIVE_DATA):
        out.append(R("safety.sensitive_data", dim, "high", "pass", title,
                     Text("El prompt menciona qué datos sensibles no pedir.",
                          "The prompt names the sensitive data it must not request.")))
    else:
        out.append(R("safety.sensitive_data", dim, "high", "fail", title,
                     Text("El prompt no prohíbe pedir contraseñas, tarjetas, documentos o datos bancarios.",
                          "The prompt doesn't forbid asking for passwords, cards, IDs or bank details."),
                     Text("Agregá en '# Límites' la lista de datos que nunca pide y qué hacer si el usuario empieza a dictarlos.",
                          "Add to '# Guardrails' the data it must never ask for and what to do if the user starts reading them out.")))
    retention = dig(c.ps, "privacy.retention_days", -1)
    title = Text("Retención de conversaciones", "Conversation retention")
    if retention in (-1, None):
        out.append(R("safety.retention", dim, "medium", "fail", title,
                     Text("Las conversaciones se guardan sin plazo.", "Conversations are kept indefinitely."),
                     Text("Definí un plazo de retención acorde a la política de datos del cliente (por ejemplo, 30 a 90 días).",
                          "Set a retention period that matches the customer's data policy (for example 30-90 days).")))
    else:
        out.append(R("safety.retention", dim, "medium", "pass", title,
                     Text(f"Retención de {retention} días.", f"{retention}-day retention.")))
    dc = c.ps.get("data_collection") or {}
    pii_fields = [k for k in dc if any(h in tu.normalize(k) for h in PII_FIELD_HINTS)]
    if pii_fields:
        redaction = dig(c.ps, "privacy.conversation_history_redaction.enabled", False)
        title = Text("Redacción de datos personales", "PII redaction")
        out.append(R("safety.redaction", dim, "medium", "pass" if redaction else "fail", title,
                     Text("Se recolectan datos personales con redacción activa." if redaction else
                          f"Se recolectan datos personales ({', '.join(pii_fields)}) sin redacción del historial.",
                          "Personal data is collected with redaction on." if redaction else
                          f"Personal data is collected ({', '.join(pii_fields)}) without history redaction."),
                     None if redaction else Text("Activá la redacción del historial o dejá de guardar esos campos.",
                                                 "Enable history redaction or stop storing those fields.")))
    auth = dig(c.ps, "auth.enable_auth", False)
    allow = dig(c.ps, "auth.allowlist", []) or []
    title = Text("Quién puede iniciar conversaciones", "Who can start conversations")
    if auth or allow:
        out.append(R("safety.access", dim, "medium", "pass", title,
                     Text("Acceso restringido (autenticación o lista de dominios).",
                          "Access is restricted (auth or domain allowlist).")))
    else:
        out.append(R("safety.access", dim, "medium", "fail", title,
                     Text("Agente público sin lista de dominios: cualquiera con el id puede abrir sesiones y consumir créditos.",
                          "Public agent with no domain allowlist: anyone with the id can open sessions and burn credits."),
                     Text("Para un widget en la web, agregá el dominio del cliente a la allowlist; para apps, usá URLs firmadas.",
                          "For a web widget, add the customer's domain to the allowlist; for apps, use signed URLs.")))
    daily = dig(c.ps, "call_limits.daily_limit", 100000)
    title = Text("Tope diario de conversaciones", "Daily conversation cap")
    if isinstance(daily, (int, float)) and daily >= 100000:
        out.append(R("safety.daily_cap", dim, "low", "fail", title,
                     Text("El tope diario está en el valor por defecto (100.000).",
                          "The daily cap is at its default (100,000)."),
                     Text("Fijá un tope acorde al volumen esperado: limita el daño de un abuso o de un bucle.",
                          "Set a cap in line with expected volume: it limits the damage of abuse or a loop.")))
    else:
        out.append(R("safety.daily_cap", dim, "low", "pass", title,
                     Text(f"Tope diario: {daily}.", f"Daily cap: {daily}.")))
    return out


# ----------------------------------------------- 9. Evaluation & data
@check
def evaluation(c: Ctx) -> List[RuleResult]:
    dim = "evaluation"
    out = []
    crit = dig(c.ps, "evaluation.criteria", []) or []
    title = Text("Criterios de evaluación", "Evaluation criteria")
    if len(crit) >= 2:
        out.append(R("eval.criteria", dim, "high", "pass", title,
                     Text(f"{len(crit)} criterios de éxito definidos.", f"{len(crit)} success criteria defined.")))
    elif len(crit) == 1:
        out.append(R("eval.criteria", dim, "high", "partial", title,
                     Text("Un solo criterio de éxito.", "Only one success criterion."),
                     Text("Sumá al menos uno de resultado (tarea completa) y uno de calidad (no inventó, derivó bien).",
                          "Add at least one outcome criterion (task done) and one quality criterion (no hallucination, correct handoff).")))
    else:
        out.append(R("eval.criteria", dim, "high", "fail", title,
                     Text("Sin criterios de evaluación: no hay forma de medir si el agente cumple su objetivo.",
                          "No evaluation criteria: there is no way to measure whether the agent meets its goal."),
                     Text("Definí dos a cinco criterios: tarea completada, derivación correcta, sin información inventada.",
                          "Define two to five criteria: task completed, correct handoff, no made-up information.")))
    dc = c.ps.get("data_collection") or {}
    title = Text("Recolección de datos", "Data collection")
    if dc:
        out.append(R("eval.data_collection", dim, "medium", "pass", title,
                     Text(f"{len(dc)} campo(s) estructurado(s) por conversación.",
                          f"{len(dc)} structured field(s) per conversation.")))
    else:
        out.append(R("eval.data_collection", dim, "medium", "fail", title,
                     Text("No se extraen datos estructurados: las conversaciones no alimentan métricas.",
                          "No structured data is extracted: conversations don't feed metrics."),
                     Text("Extraé 2 a 4 campos que muevan una métrica de adopción (etapa, motivo, bloqueo), sin datos personales.",
                          "Extract 2-4 fields that drive an adoption metric (stage, intent, blocker), without personal data.")))
    tests = dig(c.ps, "testing.attached_tests", []) or []
    title = Text("Pruebas automáticas", "Automated tests")
    if tests:
        out.append(R("eval.tests", dim, "low", "pass", title,
                     Text(f"{len(tests)} prueba(s) adjunta(s).", f"{len(tests)} test(s) attached.")))
    else:
        out.append(R("eval.tests", dim, "low", "fail", title,
                     Text("Sin pruebas ni simulaciones adjuntas: cada cambio al prompt se prueba a mano.",
                          "No attached tests or simulations: every prompt change is tested by hand."),
                     Text("Guardá 3 a 5 conversaciones difíciles como pruebas y corrélas antes de cada cambio.",
                          "Save 3-5 hard conversations as tests and run them before each change.")))
    return out


# ------------------------------------------------ 10. Call lifecycle
@check
def lifecycle(c: Ctx) -> List[RuleResult]:
    dim = "lifecycle"
    out = []
    has_end = "end_call" in c.system_tool_names
    title = Text("El agente puede terminar la llamada", "The agent can end the call")
    if has_end:
        out.append(R("life.end_call", dim, "high", "pass", title,
                     Text("Herramienta end_call activa.", "end_call tool enabled.")))
    else:
        out.append(R("life.end_call", dim, "high", "fail", title,
                     Text("Sin end_call: el agente no puede cortar y la llamada sigue hasta el máximo o hasta que corte el usuario.",
                          "No end_call: the agent can't hang up, so calls run until the max duration or the user hangs up."),
                     Text("Activá end_call y decí en el prompt cuándo usarlo.",
                          "Enable end_call and say in the prompt when to use it.")))
    title = Text("El prompt dice cuándo cerrar", "The prompt says when to close")
    if tu.contains_any(c.prompt, END_CALL_GUIDANCE):
        out.append(R("life.close_guidance", dim, "low", "pass", title,
                     Text("El prompt describe el cierre de la llamada.", "The prompt describes how to close the call.")))
    else:
        out.append(R("life.close_guidance", dim, "low", "fail", title,
                     Text("El prompt no describe cómo cerrar (resumen, próximo paso, despedida).",
                          "The prompt doesn't describe how to close (recap, next step, goodbye)."),
                     Text("Agregá '# Cierre': resumí el próximo paso en una frase y despedite.",
                          "Add '# Closing': state the next step in one sentence and say goodbye.")))
    mx = c.conv.get("max_duration_seconds")
    if isinstance(mx, (int, float)):
        title = Text("Duración máxima", "Maximum duration")
        if mx > 1800:
            out.append(R("life.max_duration", dim, "medium", "fail", title,
                         Text(f"Máximo de {int(mx // 60)} minutos: llamadas olvidadas abiertas consumen minutos.",
                              f"{int(mx // 60)}-minute maximum: forgotten open calls burn minutes."),
                         Text("Ajustalo a la duración real del caso más un margen (10 a 15 minutos suele alcanzar).",
                              "Set it to the real use-case length plus a margin (10-15 minutes is usually enough).")))
        elif mx < 120:
            out.append(R("life.max_duration", dim, "low", "fail", title,
                         Text(f"Máximo de {int(mx)} segundos: puede cortar conversaciones legítimas.",
                              f"{int(mx)}-second maximum: it may cut legitimate conversations."),
                         Text("Subilo a la duración real del caso.", "Raise it to the real use-case length.")))
        else:
            out.append(R("life.max_duration", dim, "medium", "pass", title,
                         Text(f"Máximo de {int(mx // 60)} minutos.", f"{int(mx // 60)}-minute maximum.")))
    title = Text("Mensaje al llegar al máximo", "Message when the maximum is reached")
    if (c.agent.get("max_conversation_duration_message") or "").strip():
        out.append(R("life.max_message", dim, "low", "pass", title,
                     Text("Hay un mensaje de cierre por tiempo.", "There is a time-limit closing message.")))
    else:
        out.append(R("life.max_message", dim, "low", "fail", title,
                     Text("Al llegar al máximo, la llamada se corta sin aviso.",
                          "When the maximum is reached, the call drops without warning."),
                     Text("Definí un mensaje corto que cierre con el próximo paso.",
                          "Set a short message that closes with the next step.")))
    silence = c.turn.get("silence_end_call_timeout", -1)
    title = Text("Silencio prolongado", "Prolonged silence")
    if (silence is None or silence < 0) and not has_end:
        out.append(R("life.silence", dim, "medium", "fail", title,
                     Text("Ni corte por silencio ni end_call: una llamada abandonada queda abierta hasta el máximo.",
                          "Neither silence timeout nor end_call: an abandoned call stays open until the maximum."),
                     Text("Activá el corte por silencio (30 a 60 s) con un mensaje de despedida.",
                          "Enable the silence timeout (30-60 s) with a goodbye message.")))
    else:
        out.append(R("life.silence", dim, "medium", "pass", title,
                     Text("Las llamadas abandonadas tienen salida.", "Abandoned calls have a way out.")))
    return out


def run_checks(ctx: Ctx) -> List[RuleResult]:
    results: List[RuleResult] = []
    for fn in CHECKS:
        results.extend(fn(ctx))
    return results
