"""Creates the demo agent in your ElevenLabs workspace from config.json.

  export ELEVENLABS_API_KEY=...   (never commit it)
  python3 scripts/crear_agente.py [--id-file PATH]

Safety: aborts if an agent with the same name already exists, creates no phone
number and does not enable a public share link. The agent id is written only to
--id-file (default: ../privado/agente-demo-id.txt, outside version control).
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "https://api.elevenlabs.io"


def call(method, path, body=None):
    req = urllib.request.Request(
        API + path, method=method,
        data=json.dumps(body).encode("utf-8") if body is not None else None,
        headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"], "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8")[:2000]
        sys.exit(f"{method} {path} failed: HTTP {e.code}: {detail}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id-file", default=os.path.join(HERE, "..", "privado", "agente-demo-id.txt"))
    args = ap.parse_args()
    if not os.environ.get("ELEVENLABS_API_KEY"):
        sys.exit("ELEVENLABS_API_KEY is not set")
    with open(os.path.join(HERE, "config.json"), encoding="utf-8") as f:
        config = json.load(f)
    existing = call("GET", "/v1/convai/agents?page_size=100&search=" + urllib.request.quote(config["name"]))
    if any(a.get("name") == config["name"] for a in existing.get("agents", [])):
        sys.exit("An agent with this name already exists; not creating a duplicate.")
    created = call("POST", "/v1/convai/agents/create", config)
    agent_id = created["agent_id"]
    os.makedirs(os.path.dirname(os.path.abspath(args.id_file)), exist_ok=True)
    with open(args.id_file, "w", encoding="utf-8") as f:
        f.write(agent_id + "\n")
    print("created; id written to", os.path.abspath(args.id_file))


if __name__ == "__main__":
    main()
