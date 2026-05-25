from __future__ import annotations

import os
from dataclasses import dataclass
import mimetypes
import base64
import re
from typing import Any
from urllib.parse import urljoin

import requests


@dataclass(frozen=True)
class AlibabaTtsSettings:
    token: str
    base_url: str = "https://dashscope.aliyuncs.com"
    clone_path: str = "/api/v1/services/audio/tts/customization"
    synthesis_path: str = "/api/v1/services/aigc/multimodal-generation/generation"
    enrollment_model: str = "qwen-voice-enrollment"
    synthesis_model: str = "qwen3-tts-vc-2026-01-22"
    timeout_s: int = 60


def settings_from_env(api_key: str) -> AlibabaTtsSettings:
    return AlibabaTtsSettings(
        token=(api_key or "").strip(),
        base_url=(os.getenv("ALIBABA_TTS_BASE_URL") or "https://dashscope.aliyuncs.com").strip(),
        clone_path=(os.getenv("ALIBABA_TTS_CLONE_PATH") or "/api/v1/services/audio/tts/customization").strip(),
        synthesis_path=(
            os.getenv("ALIBABA_TTS_SYNTH_PATH")
            or "/api/v1/services/aigc/multimodal-generation/generation"
        ).strip(),
        enrollment_model=(os.getenv("ALIBABA_TTS_ENROLLMENT_MODEL") or "qwen-voice-enrollment").strip(),
        synthesis_model=(os.getenv("ALIBABA_TTS_MODEL") or "qwen3-tts-vc-2026-01-22").strip(),
        timeout_s=60,
    )


class AlibabaTtsClient:
    def __init__(self, settings: AlibabaTtsSettings):
        self.settings = settings
        self.session = requests.Session()

    def _url(self, path: str) -> str:
        return urljoin(self.settings.base_url.rstrip("/") + "/", path.lstrip("/"))

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.settings.token}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _extract_voice_id(data: dict[str, Any]) -> str:
        return str(
            data.get("voice_id")
            or data.get("voice")
            or (data.get("data") or {}).get("voice_id")
            or (data.get("data") or {}).get("voice")
            or (data.get("output") or {}).get("voice")
            or (data.get("output") or {}).get("voice_id")
            or (((data.get("output") or {}).get("voices") or [None])[0] or "")
            or ""
        ).strip()

    @staticmethod
    def _extract_audio_url(data: dict[str, Any]) -> str:
        return str(
            data.get("audio_url")
            or (data.get("data") or {}).get("audio_url")
            or (data.get("output") or {}).get("audio_url")
            or ((data.get("output") or {}).get("audio") or {}).get("url")
            or ((data.get("output") or {}).get("audio") or {}).get("data")
            or ""
        ).strip()

    @staticmethod
    def _build_preferred_name() -> str:
        raw = (os.getenv("ALIBABA_TTS_PREFERRED_NAME") or "guanyu").strip().lower()
        normalized = re.sub(r"[^a-z]", "", raw)
        if not normalized:
            normalized = "guanyu"
        return normalized[:16]

    def clone_voice(self, sample_path: str, sample_name: str) -> str:
        with open(sample_path, "rb") as f:
            raw = f.read()
        mime_type, _ = mimetypes.guess_type(sample_name)
        mime = mime_type or "audio/wav"
        b64 = base64.b64encode(raw).decode("ascii")
        data_uri = f"data:{mime};base64,{b64}"
        preferred_name = self._build_preferred_name()
        payload = {
            "model": self.settings.enrollment_model,
            "input": {
                "action": "create",
                "target_model": self.settings.synthesis_model,
                "preferred_name": preferred_name,
                "audio": {"data": data_uri},
            },
        }
        response = self.session.post(
            self._url(self.settings.clone_path),
            headers=self._headers(),
            json=payload,
            timeout=self.settings.timeout_s,
        )
        try:
            response.raise_for_status()
        except requests.RequestException as exc:
            detail = (response.text or str(exc) or "")[:400]
            raise RuntimeError(f"音色复刻接口请求失败：HTTP {response.status_code}，{detail}") from exc
        data = response.json() if response.content else {}
        return self._extract_voice_id(data)

    def synthesize(self, voice_model_id: str, text: str) -> str:
        payload = {
            "model": self.settings.synthesis_model,
            "input": {
                "text": text,
                "voice": voice_model_id,
            },
            "parameters": {
                "format": "mp3",
            },
        }
        response = self.session.post(
            self._url(self.settings.synthesis_path),
            headers=self._headers(),
            json=payload,
            timeout=self.settings.timeout_s,
        )
        try:
            response.raise_for_status()
        except requests.RequestException as exc:
            detail = (response.text or str(exc) or "")[:400]
            raise RuntimeError(f"语音合成接口请求失败：HTTP {response.status_code}，{detail}") from exc
        data = response.json() if response.content else {}
        return self._extract_audio_url(data)

    def probe_clone_capability(self) -> tuple[bool, str]:
        payload = {"model": self.settings.enrollment_model, "input": {"action": "create"}}
        response = self.session.post(
            self._url(self.settings.clone_path),
            headers=self._headers(),
            json=payload,
            timeout=self.settings.timeout_s,
        )
        if response.status_code in {401, 403}:
            return False, f"鉴权或权限失败（HTTP {response.status_code}）"
        return True, f"接口可达（HTTP {response.status_code}）"

    def probe_synthesis_capability(self) -> tuple[bool, str]:
        payload = {
            "model": self.settings.synthesis_model,
            "input": {"text": "你好", "voice": "probe_voice"},
            "parameters": {"format": "mp3"},
        }
        response = self.session.post(
            self._url(self.settings.synthesis_path),
            headers=self._headers(),
            json=payload,
            timeout=self.settings.timeout_s,
        )
        if response.status_code in {401, 403}:
            return False, f"鉴权或权限失败（HTTP {response.status_code}）"
        return True, f"接口可达（HTTP {response.status_code}）"
