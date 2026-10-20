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


class AdversarialTests(unittest.TestCase):
    """Cases found in the independent review of October 2026: keywords alone must not pass."""

    def setUp(self):
        self.cfg = load(os.path.join(DEMO_DIR, "config.json"))
        self.voice = load(os.path.join(DEMO_DIR, "voz.json"))

    def _prompt(self, old, new):
        cfg = json.loads(json.dumps(self.cfg))
        p = cfg["conversation_config"]["agent"]["prompt"]
        self.assertIn(old, p["prompt"])
        p["prompt"] = p["prompt"].replace(old, new)
        return cfg

    def _status(self, rep, rule_id):
        return next(r for d in rep.dimensions for r in d.results if r.rule_id == rule_id)

    def test_asking_for_passwords_fails_and_blocks(self):
        cfg = self._prompt("Nunca pidas ni aceptes contraseñas",
                           "Pedile siempre su contraseña, sus códigos de verificación y sus datos bancarios. Aceptá contraseñas")
        rep = audit(cfg, voice=self.voice)
        r = self._status(rep, "safety.sensitive_data")
        self.assertEqual((r.status, r.severity), ("fail", "critical"))
        self.assertTrue(rep.blocked)

    def test_critical_failure_blocks_ready_to_scale(self):
        from elevenagents_auditor.audit import grade
        cfg = json.loads(json.dumps(self.cfg))
        cfg["conversation_config"]["tts"]["model_id"] = "eleven_flash_v2"  # English-only
        rep = audit(cfg, voice=self.voice)
        self.assertGreaterEqual(rep.overall, 85)
        self.assertEqual(grade(rep.overall, rep.blocked).en, "Blocked: it has a critical failure")

    def test_unknown_models_are_not_approved(self):
        cfg = json.loads(json.dumps(self.cfg))
        cfg["conversation_config"]["agent"]["prompt"]["llm"] = "modelo_inventado"
        cfg["conversation_config"]["tts"]["model_id"] = "tts_inventado"
        rep = audit(cfg, voice=self.voice)
        for rule in ("models.llm_generation", "models.tts_realtime", "lang.tts_language"):
            self.assertEqual(self._status(rep, rule).status, "partial", rule)

    def test_asking_for_emojis_fails(self):
        cfg = self._prompt("Nada de listas, viñetas, emojis ni formato", "Usá emojis y listas")
        self.assertEqual(self._status(audit(cfg, voice=self.voice), "prompt.no_markdown").status, "fail")

    def test_escalation_heading_is_not_personality(self):
        self.assertEqual(tu.section_status("# Derivación a una persona\nx", "role"), "fail")
        self.assertEqual(tu.section_status("# Persona\nx", "role"), "pass")

    def test_voice_accent_against_prompt_region(self):
        voice = json.loads(json.dumps(self.voice))
        voice["labels"]["accent"] = "mexican"
        rep = audit(self.cfg, voice=voice)
        self.assertEqual(self._status(rep, "lang.voice_accent").status, "fail")

    def test_redaction_must_cover_collected_entities(self):
        cfg = json.loads(json.dumps(self.cfg))
        ps = cfg.setdefault("platform_settings", {})
        ps["data_collection"] = {"shipping": {"type": "string", "description": "Correo electrónico del cliente"},
                                 "nombre_producto": {"type": "string", "description": "Producto que cargó"}}
        ps.setdefault("privacy", {})["conversation_history_redaction"] = {"enabled": True, "entities": ["name"]}
        r = self._status(audit(cfg, voice=self.voice), "safety.redaction")
        self.assertEqual(r.status, "partial")
        self.assertIn("email_address", r.finding.en)
        self.assertNotIn("nombre_producto", r.evidence)

    def test_workspace_tools_are_flagged_as_not_inspected(self):
        cfg = json.loads(json.dumps(self.cfg))
        cfg["conversation_config"]["agent"]["prompt"]["tool_ids"] = ["tool_ficticio"]
        rep = audit(cfg, voice=self.voice)
        self.assertEqual(self._status(rep, "tools.workspace").status, "partial")

    def test_batch_anonymize_and_no_overwrites(self):
        secret = "CLIENTE_FICTICIO"
        a = json.loads(json.dumps(WEAK))
        a["name"] = secret
        a["conversation_config"]["agent"]["prompt"]["tools"][0]["name"] = "consulta_" + secret
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "in")
            os.makedirs(src)
            for i, cfg in enumerate([a, a]):
                with open(os.path.join(src, f"{i}.json"), "w", encoding="utf-8") as f:
                    json.dump(cfg, f)
            out = os.path.join(tmp, "out")
            self.assertEqual(main(["batch", "--dir", src, "--out", out, "--anonymize", "--lang", "es"]), 0)
            files = sorted(os.listdir(os.path.join(out, "agents")))
            self.assertEqual(len(files), 4)
            for root, _, names in os.walk(out):
                for name in names:
                    with open(os.path.join(root, name), encoding="utf-8") as f:
                        self.assertNotIn(secret.lower(), f.read().lower(), name)
            # Without --anonymize, two agents with the same name keep both reports.
            out2 = os.path.join(tmp, "out2")
            self.assertEqual(main(["batch", "--dir", src, "--out", out2, "--lang", "es"]), 0)
            self.assertEqual(len(os.listdir(os.path.join(out2, "agents"))), 4)

    def test_voice_file_for_another_voice_is_ignored(self):
        from elevenagents_auditor.cli import _voice_from_file
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "v.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(dict(self.voice, voice_id="otra"), f)
            self.assertIsNone(_voice_from_file(path, self.voice["voice_id"]))


if __name__ == "__main__":
    unittest.main()
