"""Turns rule results into dimension scores and an overall score."""
from typing import Any, Dict, Optional

from .model import STATUS_CREDIT, AuditReport, DimensionScore, Text
from .rules import DIMENSIONS, Ctx, run_checks


def audit(cfg: Dict[str, Any], voice: Optional[Dict[str, Any]] = None,
          region: Optional[str] = None) -> AuditReport:
    ctx = Ctx(cfg, voice=voice, region=region)
    results = run_checks(ctx)
    dims = []
    for key, name in DIMENSIONS.items():
        rs = [r for r in results if r.dimension == key]
        scored = [r for r in rs if r.status in STATUS_CREDIT]
        total = sum(r.weight for r in scored)
        score = None
        if total:
            score = round(100.0 * sum(r.weight * STATUS_CREDIT[r.status] for r in scored) / total, 1)
        dims.append(DimensionScore(key, name, score, rs))
    applicable = [d.score for d in dims if d.score is not None]
    overall = round(sum(applicable) / len(applicable), 1) if applicable else None
    notes = []
    if voice is None:
        notes.append(Text("Sin metadatos de voz: los controles de acento quedaron fuera.",
                          "No voice metadata: accent checks were skipped."))
    if ctx.region:
        notes.append(Text(f"Región del público considerada: {ctx.region}.",
                          f"Audience region assumed: {ctx.region}."))
    return AuditReport(
        agent_name=cfg.get("name") or "(sin nombre)",
        agent_id=cfg.get("agent_id") or "",
        overall=overall,
        dimensions=dims,
        context_notes=notes,
        meta={
            "language": ctx.lang,
            "llm": ctx.p.get("llm"),
            "tts_model": ctx.tts.get("model_id"),
            "voice_name": (voice or {}).get("name"),
        },
    )


def grade(score: Optional[float], blocked: bool = False) -> Text:
    if score is None:
        return Text("sin datos", "no data")
    if blocked:
        return Text("Bloqueado: tiene una falla crítica", "Blocked: it has a critical failure")
    if score >= 85:
        return Text("Listo para escalar", "Ready to scale")
    if score >= 70:
        return Text("Sólido, con ajustes", "Solid, needs polish")
    if score >= 50:
        return Text("Brechas a cerrar antes de escalar", "Gaps to close before scaling")
    return Text("Requiere rediseño", "Needs rework")
