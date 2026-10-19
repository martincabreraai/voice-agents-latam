import json
import os
import tempfile
import unittest

from elevenagents_auditor import textutil as tu
from elevenagents_auditor.audit import audit
from elevenagents_auditor.cli import main
from elevenagents_auditor.report import render_batch_markdown, render_html, render_markdown

HERE = os.path.dirname(os.path.abspath(__file__))
DEMO_DIR = os.path.join(HERE, "..", "..", "agente-rioplatense")


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# A deliberately weak agent: Spanish, English-only TTS, no guardrails, no evaluation.
WEAK = {
    "name": "Weak agent",
    "conversation_config": {
        "agent": {
            "first_message": "Hello, welcome to our company, how can I help you today with your account and orders",
            "language": "es",
            "prompt": {"prompt": "Eres un asistente. Responde preguntas.", "llm": "gemini-2.0-flash",
                       "temperature": 0.9, "built_in_tools": {}, "tools": [
                           {"type": "webhook", "name": "lookup_order", "description": "",
                            "api_schema": {"query_params_schema": {"properties": {"id": {"type": "string"}}}}}]},
        },
        "tts": {"model_id": "eleven_flash_v2", "voice_id": "x"},
        "turn": {"turn_timeout": 2, "soft_timeout_config": {"timeout_seconds": 2,
                                                            "message": "Hhmmmm...yeah give me a second..."}},
        "conversation": {"max_duration_seconds": 3600},
    },
    "platform_settings": {"privacy": {"retention_days": -1}},
}


class TextUtilTests(unittest.TestCase):
    def test_headings_es_en(self):
        p = "# Personalidad\nx\n## Goal\ny\nGUARDRAILS:\nz"
        self.assertEqual(tu.section_status(p, "role"), "pass")
        self.assertEqual(tu.section_status(p, "goal"), "pass")
        self.assertEqual(tu.section_status(p, "guardrails"), "pass")
        self.assertEqual(tu.section_status(p, "escalation"), "fail")

    def test_body_only_is_partial(self):
        self.assertEqual(tu.section_status("Si no sabes algo, deriva a un humano.", "escalation"), "partial")

    def test_voseo_word_boundaries(self):
        self.assertFalse(tu.uses_voseo("productos nuevos"))
        self.assertTrue(tu.uses_voseo("Vos tenés que fijarte"))
        self.assertFalse(tu.uses_tuteo('Nunca uses "tú".'))
        self.assertTrue(tu.uses_tuteo("Eres un asistente"))

    def test_language_detection(self):
        self.assertEqual(tu.detect_language("Hola, ¿cómo estás? Te ayudo con la tienda de tu negocio"), "es")
        self.assertEqual(tu.detect_language("Hello, how are you? I can help you with the store"), "en")


class WeakAgentTests(unittest.TestCase):
    def setUp(self):
        self.rep = audit(WEAK)
        self.gaps = {g.rule_id: g for g in self.rep.gaps()}

    def test_low_score(self):
        self.assertLess(self.rep.overall, 50)

    def test_english_only_tts_is_critical(self):
        self.assertEqual(self.gaps["lang.tts_language"].severity, "critical")

    def test_expected_gaps(self):
        for rule in ["life.end_call", "eval.criteria", "safety.sensitive_data", "first.language",
                     "turns.soft_timeout_language", "tools.description.lookup_order", "tools.params.lookup_order",
                     "models.llm_generation", "life.max_duration", "safety.retention", "prompt.length"]:
            self.assertIn(rule, self.gaps, rule)

    def test_every_gap_has_bilingual_recommendation(self):
        for g in self.rep.gaps():
            self.assertTrue(g.recommendation and g.recommendation.es and g.recommendation.en, g.rule_id)


class DemoAgentTests(unittest.TestCase):
    def setUp(self):
        self.cfg = load(os.path.join(DEMO_DIR, "config.json"))
        self.voice = load(os.path.join(DEMO_DIR, "voz.json"))

    def test_demo_scores_high(self):
        rep = audit(self.cfg, voice=self.voice)
        self.assertGreaterEqual(rep.overall, 85)
        self.assertFalse([g for g in rep.gaps() if g.severity in ("critical", "high")])

    def test_prompt_in_sync_with_prompt_md(self):
        with open(os.path.join(DEMO_DIR, "prompt.md"), encoding="utf-8") as f:
            md = f.read().strip()
        self.assertEqual(self.cfg["conversation_config"]["agent"]["prompt"]["prompt"].strip(), md)

    def test_region_inferred_from_voice(self):
        rep = audit(self.cfg, voice=self.voice)
        self.assertTrue(any("es-AR" in n.en for n in rep.context_notes))


class RenderTests(unittest.TestCase):
    def test_renderers_both_languages(self):
        rep = audit(WEAK)
        self.assertIn("Estructura del prompt", render_markdown(rep, "es"))
        self.assertIn("Prompt structure", render_markdown(rep, "en"))
        html = render_html(rep, "en")
        self.assertTrue(html.startswith("<!doctype html>"))
        self.assertNotIn("<script", html)

    def test_batch_anonymized(self):
        reps = [audit(WEAK), audit(load(os.path.join(DEMO_DIR, "config.json")))]
        md = render_batch_markdown(reps, "en", ["Agent 01", "Agent 02"])
        self.assertIn("Agent 02", md)
        self.assertNotIn("Weak agent", md)

    def test_cli_audit_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "weak.json")
            with open(src, "w", encoding="utf-8") as f:
                json.dump(WEAK, f)
            self.assertEqual(main(["audit", "--file", src, "--out", tmp, "--lang", "es", "--name", "w"]), 0)
            self.assertTrue(os.path.exists(os.path.join(tmp, "w.es.html")))


if __name__ == "__main__":
    unittest.main()
