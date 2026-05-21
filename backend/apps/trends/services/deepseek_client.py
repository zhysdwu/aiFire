from __future__ import annotations

import json
import os
from dataclasses import dataclass

import requests


@dataclass(frozen=True)
class DeepSeekConfig:
    api_key: str
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-chat"
    timeout_s: int = 60


class DeepSeekClient:
    def __init__(self, config: DeepSeekConfig):
        self.config = config

    @classmethod
    def from_env(cls) -> "DeepSeekClient":
        api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("Missing DEEPSEEK_API_KEY")
        return cls(DeepSeekConfig(api_key=api_key))

    def chat_json(self, system: str, user: str) -> dict:
        url = f"{self.config.base_url}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }
        response = requests.post(url, headers=headers, json=payload, timeout=self.config.timeout_s)
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        if isinstance(content, str):
            return json.loads(content)
        return content
