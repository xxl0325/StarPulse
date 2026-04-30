from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Mapping

import requests


class LLMProviderError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class OpenAICompatibleProvider:
    base_url: str
    api_key: str
    model: str
    timeout: int = 60

    def generate(
        self,
        *,
        system_prompt: str,
        payload: Mapping[str, Any],
        temperature: float = 0.2,
    ) -> str:
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        body = {
            "model": self.model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=2)},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        response = requests.post(url, headers=headers, json=body, timeout=self.timeout)
        if response.status_code >= 400:
            raise LLMProviderError(f"LLM request failed with status {response.status_code}")
        data = response.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMProviderError("LLM response does not contain a chat completion") from exc

