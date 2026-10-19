# Voice agents for LATAM: an adoption toolkit for ElevenAgents

**Martín Cabrera** · Rosario, Argentina · [LinkedIn](https://www.linkedin.com/in/martincabreraai)
I design programs that get large audiences to adopt technology: 3,500+ professionals in AI programs since 2023 and 2,838 trained on Meta's ad platforms. I've been an ElevenLabs customer since February 2023.

This repo has two small, working pieces built around one question: *how do you help hundreds of customers get real value from their voice agents, in Spanish, without doing it one account at a time?*

| Piece | What it is |
|---|---|
| [**elevenagents-auditor**](elevenagents-auditor/) | A Python CLI that reads an ElevenAgents configuration (from the API or a JSON export) and scores it against a 10-dimension rubric for Spanish voice agents. It covers prompt structure, first message, language and regional voice, latency, turn-taking, tools, knowledge base, guardrails, evaluation and call lifecycle. Reports are in Markdown and HTML, in English and Spanish. A batch mode audits a whole workspace and shows which gaps repeat across agents, which is where programs come from. Read-only, no dependencies, with tests. |
| [**agente-rioplatense**](agente-rioplatense/) | *Sol*, a demo onboarding agent in Rioplatense Spanish for a fictional SaaS. It is designed for an activation metric (one more setup step done per call), with voseo end to end, an Argentine voice, escalation rules, guardrails for sensitive data, and evaluation criteria and data collection from day one. It scores 95/100 on the auditor. |

Both are working prototypes of a core customer-adoption task: proactively auditing customer agents' prompts, configurations and feature setup to find gaps, and turning the findings into recommendations that drive deeper adoption.

```bash
cd elevenagents-auditor
python3 -m unittest discover -s tests -t . -v
python3 -m elevenagents_auditor audit --file ../agente-rioplatense/config.json --voice ../agente-rioplatense/voz.json --out reports
```

Requires Python 3.9+. No third-party packages. Live mode needs `ELEVENLABS_API_KEY` in the environment and only makes `GET` requests.

*The company in the demo (Tiendalia) is fictional. No customer data is included in this repository.*

License: MIT.
