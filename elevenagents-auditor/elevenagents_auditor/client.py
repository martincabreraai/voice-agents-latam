"""Read-only ElevenLabs API client (GET only). Uses ELEVENLABS_API_KEY from the environment.

The auditor never writes to an account: it only lists and reads agents and voices.
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Iterator, Optional

BASE = os.environ.get("ELEVENLABS_API_BASE", "https://api.elevenlabs.io")


class ApiError(RuntimeError):
    pass


def _key() -> str:
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise ApiError("ELEVENLABS_API_KEY is not set")
    return key


def _get(path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    req = urllib.request.Request(url, headers={"xi-api-key": _key(), "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:  # never echo headers (they hold the key)
        raise ApiError(f"GET {path} failed: HTTP {e.code}") from None


def get_agent(agent_id: str) -> Dict[str, Any]:
    return _get(f"/v1/convai/agents/{urllib.parse.quote(agent_id)}")


def list_agents(page_size: int = 100) -> Iterator[Dict[str, Any]]:
    cursor = None
    while True:
        data = _get("/v1/convai/agents", {"page_size": page_size, "cursor": cursor})
        for a in data.get("agents", []):
            yield a
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")


def get_voice(voice_id: str) -> Optional[Dict[str, Any]]:
    try:
        return _get(f"/v1/voices/{urllib.parse.quote(voice_id)}")
    except ApiError:
        return None
