"""OpenAI-compatible local and explicit cloud model adapters."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


class ModelError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ModelResult:
    text: str
    model: str


class OpenAICompatibleClient:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str = "",
        timeout_seconds: float = 120.0,
    ) -> None:
        if not base_url or not model:
            raise ValueError("Model base URL and model are required")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def complete(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int = 700,
        temperature: float = 0.2,
    ) -> ModelResult:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode(),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw: Any = json.loads(response.read(2 * 1024 * 1024).decode())
        except (OSError, ValueError, urllib.error.URLError, urllib.error.HTTPError) as error:
            raise ModelError(f"Model request failed: {error}") from error
        try:
            text = str(raw["choices"][0]["message"]["content"]).strip()
        except (KeyError, IndexError, TypeError) as error:
            raise ModelError("Model returned an unsupported response") from error
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
        if not text:
            raise ModelError("Model returned an empty response")
        return ModelResult(text=text, model=str(raw.get("model") or self.model))
