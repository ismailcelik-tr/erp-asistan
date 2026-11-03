"""Ollama adapter over raw HTTP: the `ollama` Python client drops tool_calls from this server version."""

import base64
import json
import os
from pathlib import Path

import httpx

__all__ = ["OllamaLLM"]

_OLLAMA_URL = "http://localhost:11434/api/chat"
_KEEP_ALIVE = "60m"
# Default would be the model's full 262k window: minutes to load, GBs of KV cache.
_NUM_CTX = 16384
_TIMEOUT_SECONDS = 300


class OllamaLLM:
    def __init__(self, model: str | None = None, think: bool = False) -> None:
        self._model = model or os.environ.get("OLLAMA_MODEL", "gemma4:12b")
        self._think = think
        self._http = httpx.Client(timeout=_TIMEOUT_SECONDS)

    def chat(self, messages: list[dict], tools: list[dict]) -> dict:
        msg = self._post({"messages": messages, "tools": tools})
        calls = msg.get("tool_calls") or []
        return {
            "content": msg.get("content") or "",
            "tool_calls": [{"name": c["function"]["name"], "arguments": c["function"]["arguments"]} for c in calls],
        }

    def extract(self, prompt: str, image: Path, fmt: dict | str) -> dict:
        """Structured output from an image. fmt: "json" or a JSON schema."""
        encoded = base64.b64encode(Path(image).read_bytes()).decode()
        msg = self._post({
            "messages": [{"role": "user", "content": prompt, "images": [encoded]}],
            "format": fmt,
        })
        return json.loads(msg["content"])

    def _post(self, body: dict) -> dict:
        body |= {
            "model": self._model,
            "stream": False,
            "think": self._think,
            "keep_alive": _KEEP_ALIVE,
            "options": {"temperature": 0, "num_ctx": _NUM_CTX},
        }
        resp = self._http.post(_OLLAMA_URL, json=body)
        resp.raise_for_status()
        return resp.json()["message"]
