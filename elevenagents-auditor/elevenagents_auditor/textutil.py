"""Light-weight text heuristics for prompts written in Spanish or English.

No external NLP dependencies on purpose: the auditor has to run anywhere, on
thousands of configs, in seconds. Heuristics are conservative and every rule
that relies on them says so in the README.
"""
import re
import unicodedata
from typing import Dict, List, Optional


def normalize(text: str) -> str:
    """Lowercase and strip accents so 'Límites' matches 'limites'."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.lower()


HEADING_RE = re.compile(r"^\s*(#{1,6})\s*(.+?)\s*#*\s*$", re.MULTILINE)
LABEL_RE = re.compile(r"^\s*\**([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ /&]{2,40})\**\s*:?\s*$", re.MULTILINE)


def headings(prompt: str) -> List[str]:
    """Markdown headings plus ALL-CAPS label lines ('GUARDRAILS:')."""
    found = [normalize(m.group(2)) for m in HEADING_RE.finditer(prompt or "")]
    found += [normalize(m.group(1)) for m in LABEL_RE.finditer(prompt or "")]
    return found


# Section synonyms (normalized, accent-free). Spanish first, English second.
SECTION_KEYWORDS: Dict[str, List[str]] = {
    "role": ["personalidad", "identidad", "rol", "quien sos", "quien eres", "persona",
             "personality", "identity", "role"],
    "goal": ["objetivo", "mision", "tarea", "proposito", "goal", "objective", "task", "mission"],
    "tone": ["tono", "estilo", "forma de hablar", "tone", "style", "voice and style"],
    "guardrails": ["limites", "restricciones", "reglas", "guardrails", "boundaries", "rules",
                   "lo que no", "prohibido"],
    "environment": ["entorno", "contexto", "environment", "context"],
    "errors": ["manejo de errores", "errores", "error handling", "errors", "fallback"],
    "escalation": ["derivacion", "escalamiento", "escalar", "transferencia", "handoff",
                   "escalation", "human handoff"],
    "tools": ["herramientas", "tools"],
}

# Body-text signals used when there is no explicit heading.
BODY_SIGNALS: Dict[str, List[str]] = {
    "role": ["sos ", "eres ", "you are "],
    "goal": ["tu objetivo", "your goal", "tu tarea", "your task"],
    "tone": ["tono", "tone", "amable", "friendly", "calido", "warm"],
    "guardrails": ["nunca ", "never ", "no debes", "no tenes que", "do not ", "don't "],
    "environment": ["por telefono", "por voz", "over the phone", "by voice", "llamada"],
    "errors": ["no lo se", "no se la respuesta", "no sabes", "no sabe", "if you don't know",
               "if you do not know", "no entendiste", "didn't understand", "si falla",
               "if a tool fails", "no inventes", "never invent", "don't make up"],
    "escalation": ["humano", "una persona", "agente humano", "deriv", "transfer", "escal",
                   "human", "soporte", "support team", "supervisor"],
    "tools": [],
}


def section_status(prompt: str, section: str) -> str:
    """'pass' if there is a heading, 'partial' if only mentioned in the body, else 'fail'."""
    heads = headings(prompt)
    for h in heads:
        for kw in SECTION_KEYWORDS[section]:
            if kw in h:
                return "pass"
    body = normalize(prompt)
    for kw in BODY_SIGNALS[section]:
        if kw in body:
            return "partial"
    return "fail"


def contains_any(text: str, keywords: List[str]) -> bool:
    t = normalize(text)
    return any(normalize(k) in t for k in keywords)


ES_MARKERS = [" el ", " la ", " de ", " que ", " y ", " los ", " para ", " con ", " por ", " una ",
              " es ", " no ", " si ", " tu ", " su "]
EN_MARKERS = [" the ", " and ", " to ", " of ", " you ", " is ", " for ", " with ", " your ",
              " are ", " this ", " that ", " if ", " not "]


def detect_language(text: str) -> Optional[str]:
    """Very small stopword vote between Spanish and English. None if unclear."""
    t = " " + re.sub(r"[^\w\s]", " ", normalize(text)) + " "
    es = sum(t.count(m) for m in ES_MARKERS)
    en = sum(t.count(m) for m in EN_MARKERS)
    if es + en < 3:
        return None
    if es >= en * 1.5:
        return "es"
    if en >= es * 1.5:
        return "en"
    return None


VOSEO = [r"vos", r"tenes", r"queres", r"podes", r"fijate", r"contame", r"decime",
         r"voseo", r"rioplatense", r"sos"]
TUTEO = [r"eres", r"tienes", r"quieres", r"puedes", r"cuentame", r"dime", r"tuteo"]


def _has_word(text: str, words: List[str]) -> bool:
    t = normalize(text)
    return any(re.search(r"\b" + w + r"\b", t) for w in words)


def uses_voseo(text: str) -> bool:
    return _has_word(text, VOSEO)


def uses_tuteo(text: str) -> bool:
    # "Nunca uses tu/tuteo" is an instruction, not tuteo: ignore lines that forbid it.
    lines = [ln for ln in (text or "").splitlines()
             if not re.search(r"\b(nunca|no)\b.*\b(tu|tuteo)\b", normalize(ln))]
    return _has_word("\n".join(lines), TUTEO)


def sentence_count(text: str) -> int:
    """Counts sentences, ignoring interjections like '¡Hola!' (fewer than three words)."""
    parts = [p for p in re.split(r"[.!?…]+", text or "") if len(p.split()) >= 3]
    return len(parts)
