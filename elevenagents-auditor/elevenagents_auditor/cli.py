"""Command line interface.

  python -m elevenagents_auditor audit --file agent.json [--voice voice.json] [--region es-AR]
  python -m elevenagents_auditor audit --agent-id AGENT_ID          # needs ELEVENLABS_API_KEY
  python -m elevenagents_auditor batch --dir configs/                # many exported JSONs
  python -m elevenagents_auditor batch --all [--anonymize]           # every agent in the workspace
  python -m elevenagents_auditor export --agent-id AGENT_ID --out agent.json
"""
import argparse
import glob
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

from . import client
from .audit import audit
from .report import render_batch_csv, render_batch_markdown, render_html, render_markdown


def _load(path: str) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _voice_from_file(path: Optional[str], voice_id: Optional[str]) -> Optional[Dict[str, Any]]:
    """Accepts a single voice object, a list, or the /v2/voices response."""
    if not path:
        return None
    data = _load(path)
    voices = data.get("voices") if isinstance(data, dict) and "voices" in data else data
    if isinstance(voices, dict):
        return voices
    for v in voices or []:
        if v.get("voice_id") == voice_id:
            return v
    return None


def _slug(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE).strip().lower()
    return re.sub(r"[\s_]+", "-", text)[:60] or "agent"


def _write_reports(rep, out_dir: str, langs: List[str], stem: str) -> List[str]:
    os.makedirs(out_dir, exist_ok=True)
    written = []
    for lang in langs:
        for ext, render in (("md", render_markdown), ("html", render_html)):
            path = os.path.join(out_dir, f"{stem}.{lang}.{ext}")
            with open(path, "w", encoding="utf-8") as f:
                f.write(render(rep, lang))
            written.append(path)
    return written


def _langs(value: str) -> List[str]:
    return ["es", "en"] if value == "both" else [value]


def _fetch(agent_id: str) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    cfg = client.get_agent(agent_id)
    voice_id = (cfg.get("conversation_config") or {}).get("tts", {}).get("voice_id")
    voice = client.get_voice(voice_id) if voice_id else None
    return cfg, voice


def cmd_audit(args) -> int:
    if args.agent_id:
        cfg, voice = _fetch(args.agent_id)
    else:
        cfg = _load(args.file)
        vid = (cfg.get("conversation_config") or {}).get("tts", {}).get("voice_id")
        voice = _voice_from_file(args.voice, vid)
    rep = audit(cfg, voice=voice, region=args.region)
    stem = args.name or _slug(rep.agent_name)
    for p in _write_reports(rep, args.out, _langs(args.lang), stem):
        print(p)
    print(f"overall: {rep.overall}")
    return 0


def cmd_batch(args) -> int:
    items: List[Tuple[Dict[str, Any], Optional[Dict[str, Any]]]] = []
    if args.all:
        for a in client.list_agents():
            items.append(_fetch(a["agent_id"]))
    else:
        for path in sorted(glob.glob(os.path.join(args.dir, "*.json"))):
            data = _load(path)
            if isinstance(data, dict) and "conversation_config" in data:
                vid = data["conversation_config"].get("tts", {}).get("voice_id")
                items.append((data, _voice_from_file(args.voices, vid)))
    if not items:
        print("no agent configs found", file=sys.stderr)
        return 1
    reports = [audit(cfg, voice=v, region=args.region) for cfg, v in items]
    names = [f"Agent {i:02d}" for i in range(1, len(reports) + 1)] if args.anonymize else None
    os.makedirs(args.out, exist_ok=True)
    for lang in _langs(args.lang):
        path = os.path.join(args.out, f"summary.{lang}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(render_batch_markdown(reports, lang, names))
        print(path)
    path = os.path.join(args.out, "summary.csv")
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(render_batch_csv(reports, names))
    print(path)
    if not args.summary_only:
        for i, rep in enumerate(reports):
            stem = names[i].lower().replace(" ", "-") if names else _slug(rep.agent_name)
            if names:
                rep.agent_name = names[i]
            _write_reports(rep, os.path.join(args.out, "agents"), _langs(args.lang), stem)
    return 0


def cmd_export(args) -> int:
    cfg = client.get_agent(args.agent_id)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print(args.out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="elevenagents-auditor",
                                description="Audit ElevenAgents configurations against a voice-agent rubric.")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("audit", help="audit one agent")
    src = a.add_mutually_exclusive_group(required=True)
    src.add_argument("--file", help="exported agent JSON (GET /v1/convai/agents/{id} or create payload)")
    src.add_argument("--agent-id", help="read the agent from the API (GET only)")
    a.add_argument("--voice", help="voice metadata JSON (offline mode)")
    a.add_argument("--region", help="audience region, e.g. es-AR, es-MX (inferred if omitted)")
    a.add_argument("--lang", choices=["es", "en", "both"], default="both")
    a.add_argument("--out", default="reports")
    a.add_argument("--name", help="file stem for the reports")
    a.set_defaults(func=cmd_audit)

    b = sub.add_parser("batch", help="audit many agents and aggregate")
    bsrc = b.add_mutually_exclusive_group(required=True)
    bsrc.add_argument("--dir", help="folder with exported agent JSONs")
    bsrc.add_argument("--all", action="store_true", help="every agent in the workspace (API, GET only)")
    b.add_argument("--voices", help="voices JSON (/v2/voices response) for offline mode")
    b.add_argument("--region")
    b.add_argument("--lang", choices=["es", "en", "both"], default="both")
    b.add_argument("--out", default="reports")
    b.add_argument("--anonymize", action="store_true", help="replace agent names with Agent 01, 02…")
    b.add_argument("--summary-only", action="store_true")
    b.set_defaults(func=cmd_batch)

    e = sub.add_parser("export", help="save an agent config as JSON (GET only)")
    e.add_argument("--agent-id", required=True)
    e.add_argument("--out", required=True)
    e.set_defaults(func=cmd_export)
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except client.ApiError as exc:
        print(f"API error: {exc}", file=sys.stderr)
        return 2
