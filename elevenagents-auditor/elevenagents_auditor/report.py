"""Markdown and HTML renderers, for one agent and for a whole book of agents."""
import csv
import html
import io
from collections import Counter
from datetime import date
from typing import Dict, List, Optional

from .audit import grade
from .model import AuditReport, RuleResult, SEVERITY_ORDER
from .rules import DIMENSIONS

L = {
    "title": {"es": "Auditoría de agente ElevenAgents", "en": "ElevenAgents agent audit"},
    "agent": {"es": "Agente", "en": "Agent"},
    "date": {"es": "Fecha", "en": "Date"},
    "overall": {"es": "Puntaje general", "en": "Overall score"},
    "dimension": {"es": "Dimensión", "en": "Dimension"},
    "score": {"es": "Puntaje", "en": "Score"},
    "top": {"es": "Prioridades (de mayor a menor impacto)", "en": "Priorities (highest impact first)"},
    "detail": {"es": "Detalle por dimensión", "en": "Detail by dimension"},
    "finding": {"es": "Hallazgo", "en": "Finding"},
    "rec": {"es": "Recomendación", "en": "Recommendation"},
    "none": {"es": "Sin brechas: nada que corregir.", "en": "No gaps: nothing to fix."},
    "na": {"es": "no aplica", "en": "n/a"},
    "notes": {"es": "Notas", "en": "Notes"},
    "setup": {"es": "Configuración leída", "en": "Configuration read"},
    "severity": {"es": "Severidad", "en": "Severity"},
    "footer": {
        "es": "Generado con elevenagents-auditor. La rúbrica y el porqué de cada regla están en el README.",
        "en": "Generated with elevenagents-auditor. The rubric and the rationale for each rule are in the README.",
    },
}
SEV = {
    "critical": {"es": "crítica", "en": "critical"},
    "high": {"es": "alta", "en": "high"},
    "medium": {"es": "media", "en": "medium"},
    "low": {"es": "baja", "en": "low"},
}
ICON = {"pass": "✅", "partial": "🟡", "fail": "❌", "na": "➖"}


def _fmt(score: Optional[float], lang: str) -> str:
    return L["na"][lang] if score is None else f"{score:.0f}/100"


def _bar(score: Optional[float]) -> str:
    if score is None:
        return ""
    filled = int(round(score / 10))
    return "█" * filled + "░" * (10 - filled)


def render_markdown(rep: AuditReport, lang: str = "en", top_n: int = 5) -> str:
    out = io.StringIO()
    w = out.write
    w(f"# {L['title'][lang]}\n\n")
    w(f"**{L['agent'][lang]}:** {rep.agent_name}  \n")
    w(f"**{L['date'][lang]}:** {date.today().isoformat()}  \n")
    m = rep.meta
    w(f"**{L['setup'][lang]}:** language `{m.get('language')}` · LLM `{m.get('llm')}` · TTS `{m.get('tts_model')}`")
    if m.get("voice_name"):
        w(f" · voice `{m.get('voice_name')}`")
    w("\n\n")
    w(f"## {L['overall'][lang]}: {_fmt(rep.overall, lang)} — {grade(rep.overall).get(lang)}\n\n")
    w(f"| {L['dimension'][lang]} | {L['score'][lang]} | |\n|---|---:|---|\n")
    for d in rep.dimensions:
        w(f"| {d.name.get(lang)} | {_fmt(d.score, lang)} | {_bar(d.score)} |\n")
    w("\n")
    gaps = rep.gaps()
    w(f"## {L['top'][lang]}\n\n")
    if not gaps:
        w(L["none"][lang] + "\n\n")
    for i, r in enumerate(gaps[:top_n], 1):
        rec = r.recommendation.get(lang) if r.recommendation else ""
        w(f"{i}. **{r.title.get(lang)}** ({SEV[r.severity][lang]}) — {r.finding.get(lang)} {rec}\n")
    w("\n")
    w(f"## {L['detail'][lang]}\n\n")
    for d in rep.dimensions:
        w(f"### {d.name.get(lang)} · {_fmt(d.score, lang)}\n\n")
        for r in d.results:
            w(f"- {ICON[r.status]} **{r.title.get(lang)}** — {r.finding.get(lang)}")
            if r.is_gap and r.recommendation:
                w(f"  \n  → {r.recommendation.get(lang)}")
            w("\n")
        w("\n")
    if rep.context_notes:
        w(f"## {L['notes'][lang]}\n\n")
        for n in rep.context_notes:
            w(f"- {n.get(lang)}\n")
        w("\n")
    w(f"---\n*{L['footer'][lang]}*\n")
    return out.getvalue()


CSS = """
:root{--bg:#fbfaf7;--fg:#1d1d1f;--muted:#6b6b70;--card:#fff;--line:#e6e3dc;--ok:#1f8a4c;--mid:#b7791f;--bad:#c0392b;--bar:#2b2b2e}
@media (prefers-color-scheme:dark){:root{--bg:#141416;--fg:#ececec;--muted:#a0a0a6;--card:#1d1d20;--line:#2e2e33;--bar:#e8e8e8}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
main{max-width:880px;margin:0 auto;padding:32px 16px 64px}h1{font-size:1.6rem;margin:0 0 4px}h2{margin-top:2rem;font-size:1.2rem}
.meta{color:var(--muted);font-size:.9rem}.score{font-size:3rem;font-weight:700;line-height:1}.grade{color:var(--muted)}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin:12px 0}
table{width:100%;border-collapse:collapse}td{padding:6px 4px;border-bottom:1px solid var(--line);vertical-align:middle}
td.num{text-align:right;font-variant-numeric:tabular-nums;width:72px}.track{background:var(--line);border-radius:6px;height:8px;width:100%}
.fill{background:var(--bar);height:8px;border-radius:6px}ol li{margin-bottom:8px}.sev{font-size:.75rem;border:1px solid var(--line);border-radius:999px;padding:1px 8px;color:var(--muted)}
.r{margin:6px 0}.r .rec{color:var(--muted);margin-left:1.6em}
"""


def render_html(rep: AuditReport, lang: str = "en", top_n: int = 5) -> str:
    e = html.escape
    m = rep.meta
    rows = []
    for d in rep.dimensions:
        width = 0 if d.score is None else d.score
        rows.append(f"<tr><td>{e(d.name.get(lang))}</td><td class='num'>{e(_fmt(d.score, lang))}</td>"
                    f"<td style='width:40%'><div class='track'><div class='fill' style='width:{width}%'></div></div></td></tr>")
    gaps = rep.gaps()[:top_n]
    tops = "".join(
        f"<li><strong>{e(r.title.get(lang))}</strong> <span class='sev'>{e(SEV[r.severity][lang])}</span><br>"
        f"{e(r.finding.get(lang))} {e(r.recommendation.get(lang) if r.recommendation else '')}</li>"
        for r in gaps) or f"<p>{e(L['none'][lang])}</p>"
    detail = []
    for d in rep.dimensions:
        items = []
        for r in d.results:
            rec = (f"<div class='rec'>→ {e(r.recommendation.get(lang))}</div>"
                   if r.is_gap and r.recommendation else "")
            items.append(f"<div class='r'>{ICON[r.status]} <strong>{e(r.title.get(lang))}</strong> — "
                         f"{e(r.finding.get(lang))}{rec}</div>")
        detail.append(f"<div class='card'><h3>{e(d.name.get(lang))} · {e(_fmt(d.score, lang))}</h3>{''.join(items)}</div>")
    notes = "".join(f"<li>{e(n.get(lang))}</li>" for n in rep.context_notes)
    setup = (f"language <code>{e(str(m.get('language')))}</code> · LLM <code>{e(str(m.get('llm')))}</code> · "
             f"TTS <code>{e(str(m.get('tts_model')))}</code>")
    if m.get("voice_name"):
        setup += f" · voice <code>{e(str(m.get('voice_name')))}</code>"
    return f"""<!doctype html><html lang="{lang}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(L['title'][lang])}</title>
<style>{CSS}</style></head><body><main>
<h1>{e(L['title'][lang])}</h1>
<div class="meta">{e(L['agent'][lang])}: <strong>{e(rep.agent_name)}</strong> · {e(L['date'][lang])}: {date.today().isoformat()}<br>{setup}</div>
<div class="card"><div class="score">{e(_fmt(rep.overall, lang))}</div><div class="grade">{e(grade(rep.overall).get(lang))}</div>
<table>{''.join(rows)}</table></div>
<h2>{e(L['top'][lang])}</h2><ol>{tops}</ol>
<h2>{e(L['detail'][lang])}</h2>{''.join(detail)}
{f"<h2>{e(L['notes'][lang])}</h2><ul>{notes}</ul>" if notes else ""}
<p class="meta">{e(L['footer'][lang])}</p>
</main></body></html>
"""


# ------------------------------------------------------------------ batch
B = {
    "title": {"es": "Auditoría de la cartera de agentes", "en": "Agent book audit"},
    "agents": {"es": "Agentes auditados", "en": "Agents audited"},
    "avg": {"es": "Puntaje promedio", "en": "Average score"},
    "by_dim": {"es": "Promedio por dimensión", "en": "Average by dimension"},
    "common": {"es": "Brechas más frecuentes (señales para el playbook)",
               "en": "Most frequent gaps (signals for the playbook)"},
    "share": {"es": "% de agentes", "en": "% of agents"},
    "gap": {"es": "Brecha", "en": "Gap"},
    "per_agent": {"es": "Por agente", "en": "Per agent"},
    "bands": {"es": "Distribución", "en": "Distribution"},
    "reading": {
        "es": "Cómo leerlo: una brecha que aparece en muchos agentes no se arregla cuenta por cuenta; "
              "se arregla con un programa (un webinar, una plantilla, un paso del onboarding).",
        "en": "How to read it: a gap that shows up across many agents isn't fixed account by account; "
              "it's fixed with a program (a webinar, a template, an onboarding step).",
    },
}


def summarize(reports: List[AuditReport]) -> Dict:
    n = len(reports)
    overall = [r.overall for r in reports if r.overall is not None]
    by_dim = {}
    for key in DIMENSIONS:
        vals = [d.score for r in reports for d in r.dimensions if d.key == key and d.score is not None]
        by_dim[key] = round(sum(vals) / len(vals), 1) if vals else None
    gap_counter: Counter = Counter()
    gap_meta: Dict[str, RuleResult] = {}
    for r in reports:
        seen = set()
        for g in r.gaps():
            base = g.rule_id.split(".")[0] + "." + g.rule_id.split(".")[1]
            if base in seen:
                continue
            seen.add(base)
            gap_counter[base] += 1
            gap_meta.setdefault(base, g)
    bands = Counter(grade(r.overall).en for r in reports)
    return {"n": n, "avg": round(sum(overall) / len(overall), 1) if overall else None,
            "by_dim": by_dim, "gaps": gap_counter, "gap_meta": gap_meta, "bands": bands}


def render_batch_markdown(reports: List[AuditReport], lang: str = "en", names: Optional[List[str]] = None) -> str:
    s = summarize(reports)
    names = names or [r.agent_name for r in reports]
    out = io.StringIO()
    w = out.write
    w(f"# {B['title'][lang]}\n\n")
    w(f"**{B['agents'][lang]}:** {s['n']} · **{B['avg'][lang]}:** {_fmt(s['avg'], lang)} · "
      f"{L['date'][lang]}: {date.today().isoformat()}\n\n")
    w(f"## {B['by_dim'][lang]}\n\n| {L['dimension'][lang]} | {L['score'][lang]} | |\n|---|---:|---|\n")
    for key, name in DIMENSIONS.items():
        w(f"| {name.get(lang)} | {_fmt(s['by_dim'][key], lang)} | {_bar(s['by_dim'][key])} |\n")
    w(f"\n## {B['common'][lang]}\n\n{B['reading'][lang]}\n\n")
    w(f"| {B['gap'][lang]} | {L['severity'][lang]} | {B['share'][lang]} |\n|---|---|---:|\n")
    for base, count in s["gaps"].most_common(12):
        g = s["gap_meta"][base]
        w(f"| {g.title.get(lang)} | {SEV[g.severity][lang]} | {100 * count / s['n']:.0f}% |\n")
    w(f"\n## {B['per_agent'][lang]}\n\n| {L['agent'][lang]} | {L['overall'][lang]} | "
      + " | ".join(d.get(lang) for d in DIMENSIONS.values()) + " |\n")
    w("|---|---:|" + "---:|" * len(DIMENSIONS) + "\n")
    for name, r in sorted(zip(names, reports), key=lambda x: -(x[1].overall or 0)):
        cells = " | ".join(_fmt(d.score, lang).replace("/100", "") for d in r.dimensions)
        w(f"| {name} | {_fmt(r.overall, lang)} | {cells} |\n")
    w(f"\n---\n*{L['footer'][lang]}*\n")
    return out.getvalue()


def render_batch_csv(reports: List[AuditReport], names: Optional[List[str]] = None) -> str:
    names = names or [r.agent_name for r in reports]
    buf = io.StringIO()
    wr = csv.writer(buf)
    wr.writerow(["agent", "overall"] + list(DIMENSIONS.keys()) +
                [f"gaps_{s}" for s in SEVERITY_ORDER])
    for name, r in zip(names, reports):
        sev = Counter(g.severity for g in r.gaps())
        wr.writerow([name, r.overall] + [d.score for d in r.dimensions] + [sev.get(s, 0) for s in SEVERITY_ORDER])
    return buf.getvalue()
