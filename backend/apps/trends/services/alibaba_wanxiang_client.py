from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
import time
from typing import Any, Callable
from urllib.parse import urljoin

import requests

from apps.trends.services.digital_human_video_service import DigitalHumanVideoError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AlibabaWanxiangSettings:
    api_key: str
    api_base_url: str = "https://dashscope.aliyuncs.com"
    model_name: str = "wan2.2-s2v"
    tts_model: str = "qwen3-tts-flash"
    voice: str = "Cherry"
    language_type: str = "Chinese"
    audio_format: str = "wav"
    sample_rate: int = 24000
    resolution: str = "480P"
    poll_interval_s: float = 5
    poll_timeout_s: float = 600
    request_timeout_s: float = 60


def _clean_base_url(base_url: str) -> str:
    return (base_url or "https://dashscope.aliyuncs.com").rstrip("/") + "/"


def _extra_int(extra_config: dict[str, Any], key: str, default: int) -> int:
    value = extra_config.get(key, default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _extra_float(extra_config: dict[str, Any], key: str, default: float) -> float:
    value = extra_config.get(key, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def settings_from_engine_config(config) -> AlibabaWanxiangSettings:
    extra_config = config.extra_config if isinstance(config.extra_config, dict) else {}
    return AlibabaWanxiangSettings(
        api_key=(config.api_key or "").strip(),
        api_base_url=(config.api_base_url or extra_config.get("api_base_url") or "https://dashscope.aliyuncs.com").strip(),
        model_name=(config.model_name or extra_config.get("model_name") or "wan2.2-s2v").strip(),
        tts_model=(extra_config.get("tts_model") or "qwen3-tts-flash").strip(),
        voice=(config.voice_id or extra_config.get("voice") or "Cherry").strip(),
        language_type=(extra_config.get("language_type") or "Chinese").strip(),
        audio_format=(extra_config.get("audio_format") or "wav").strip(),
        sample_rate=_extra_int(extra_config, "sample_rate", 24000),
        resolution=(extra_config.get("resolution") or "480P").strip(),
        poll_interval_s=_extra_float(extra_config, "poll_interval_s", 5),
        poll_timeout_s=_extra_float(extra_config, "poll_timeout_s", 600),
        request_timeout_s=_extra_float(extra_config, "request_timeout_s", 60),
    )


class AlibabaWanxiangClient:
    def __init__(
        self,
        settings: AlibabaWanxiangSettings,
        *,
        session: requests.Session | None = None,
        sleep_func: Callable[[float], None] | None = None,
    ):
        self.settings = settings
        self.session = session or requests.Session()
        self.sleep = sleep_func or time.sleep

    def _url(self, path: str) -> str:
        return urljoin(_clean_base_url(self.settings.api_base_url), path.lstrip("/"))

    def _headers(self, *, async_task: bool = False, oss_resolve: bool = False) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.settings.api_key}",
            "Content-Type": "application/json",
        }
        if async_task:
            headers["X-DashScope-Async"] = "enable"
        if oss_resolve:
            headers["X-DashScope-OssResourceResolve"] = "enable"
        return headers

    def upload_file(self, file_path: Path, *, model_name: str | None = None) -> str:
        logger.info("[万象] 开始上传素材: %s", file_path.name)
        policy_response = self.session.get(
            self._url("/api/v1/uploads"),
            params={"action": "getPolicy", "model": model_name or self.settings.model_name},
            headers={"Authorization": f"Bearer {self.settings.api_key}"},
            timeout=self.settings.request_timeout_s,
        )
        self._raise_for_response(policy_response, "Failed to get Alibaba upload policy")
        data = policy_response.json().get("data") or {}
        upload_host = data.get("upload_host")
        upload_dir = data.get("upload_dir")
        if not upload_host or not upload_dir:
            raise DigitalHumanVideoError("Alibaba upload policy response is missing upload_host or upload_dir", 502)

        object_key = f"{upload_dir.rstrip('/')}/{file_path.name}"
        form_data = {
            "OSSAccessKeyId": data.get("oss_access_key_id", ""),
            "Signature": data.get("signature", ""),
            "policy": data.get("policy", ""),
            "key": object_key,
            "success_action_status": "200",
        }
        if data.get("x_oss_object_acl"):
            form_data["x-oss-object-acl"] = data["x_oss_object_acl"]
        if data.get("x_oss_forbid_overwrite"):
            form_data["x-oss-forbid-overwrite"] = data["x_oss_forbid_overwrite"]

        with file_path.open("rb") as file_obj:
            upload_response = self.session.post(
                upload_host,
                data=form_data,
                files={"file": (file_path.name, file_obj)},
                timeout=self.settings.request_timeout_s,
            )
        self._raise_for_response(upload_response, "Failed to upload file to Alibaba OSS")
        logger.info("[万象] 素材上传成功: %s", object_key)
        return f"oss://{object_key}"

    def synthesize_tts(self, script: str) -> str:
        payload = {
            "model": self.settings.tts_model,
            "input": {
                "text": script,
                "voice": self.settings.voice,
                "language_type": self.settings.language_type,
            },
        }
        response = self.session.post(
            self._url("/api/v1/services/aigc/multimodal-generation/generation"),
            headers=self._headers(),
            json=payload,
            timeout=self.settings.request_timeout_s,
        )
        self._raise_for_response(response, "Alibaba TTS request failed")
        payload = response.json()
        audio_url = self._extract_audio_url(payload)
        if not audio_url:
            raise DigitalHumanVideoError("Alibaba TTS response did not include an audio URL", 502)
        return audio_url

    def create_video_task(self, *, avatar_url: str, audio_url: str) -> str:
        logger.info("[万象] 开始创建视频任务")
        payload = {
            "model": self.settings.model_name,
            "input": {
                "image_url": avatar_url,
                "audio_url": audio_url,
            },
            "parameters": {
                "resolution": self.settings.resolution,
            },
        }
        response = self.session.post(
            self._url("/api/v1/services/aigc/image2video/video-synthesis"),
            headers=self._headers(async_task=True, oss_resolve=True),
            json=payload,
            timeout=self.settings.request_timeout_s,
        )
        self._raise_for_response(response, "Alibaba Wanxiang task creation failed")
        task_id = ((response.json().get("output") or {}).get("task_id") or "").strip()
        if not task_id:
            raise DigitalHumanVideoError("Alibaba Wanxiang response did not include a task id", 502)
        logger.info("[万象] 任务创建成功: task_id=%s", task_id)
        return task_id

    def wait_for_video_url(self, task_id: str) -> str:
        logger.info("[万象] 开始轮询任务: task_id=%s timeout=%ss interval=%ss", task_id, self.settings.poll_timeout_s, self.settings.poll_interval_s)
        deadline = time.monotonic() + self.settings.poll_timeout_s
        while time.monotonic() <= deadline:
            response = self.session.get(
                self._url(f"/api/v1/tasks/{task_id}"),
                headers={"Authorization": f"Bearer {self.settings.api_key}"},
                timeout=self.settings.request_timeout_s,
            )
            self._raise_for_response(response, "Alibaba Wanxiang task polling failed")
            payload = response.json()
            output = payload.get("output") or {}
            task_status = (output.get("task_status") or output.get("status") or "").upper()
            logger.info("[万象] 轮询状态: task_id=%s status=%s", task_id, task_status or "UNKNOWN")
            if task_status == "SUCCEEDED":
                video_url = self._extract_video_url(output)
                if not video_url:
                    raise DigitalHumanVideoError("Alibaba Wanxiang task succeeded without a video URL", 502)
                logger.info("[万象] 任务成功: task_id=%s", task_id)
                return video_url
            if task_status in {"FAILED", "CANCELED", "UNKNOWN"}:
                message = output.get("message") or output.get("code") or "Alibaba Wanxiang task failed"
                raise DigitalHumanVideoError(str(message), 502)
            self.sleep(self.settings.poll_interval_s)
        raise DigitalHumanVideoError(
            f"Alibaba Wanxiang task timed out (task_id={task_id}, timeout={int(self.settings.poll_timeout_s)}s)",
            504,
        )

    def download_video(self, video_url: str, output_path: Path) -> None:
        logger.info("[万象] 开始下载视频: %s", video_url)
        response = self.session.get(video_url, stream=True, timeout=self.settings.request_timeout_s)
        self._raise_for_response(response, "Failed to download Alibaba Wanxiang video")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("wb") as dest:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    dest.write(chunk)
        logger.info("[万象] 视频下载完成: %s", output_path)

    def generate_video(
        self,
        *,
        script: str,
        audio_mode: str,
        audio_path: Path | None,
        avatar_image_path: Path | None = None,
        avatar_image_url: str = "",
        output_path: Path,
    ) -> dict:
        avatar_url = (avatar_image_url or "").strip()
        if not avatar_url:
            if avatar_image_path is None:
                raise DigitalHumanVideoError("Alibaba Wanxiang avatar image is required", 400)
            avatar_url = self.upload_file(avatar_image_path)
        if audio_mode == "default":
            audio_url = self.synthesize_tts(script)
        else:
            if audio_path is None:
                raise DigitalHumanVideoError("Audio file is required for Alibaba Wanxiang upload mode", 400)
            audio_url = self.upload_file(audio_path)
        task_id = self.create_video_task(avatar_url=avatar_url, audio_url=audio_url)
        video_url = self.wait_for_video_url(task_id)
        self.download_video(video_url, output_path)
        return {"task_id": task_id, "source_video_url": video_url}

    def probe_video_capability(self) -> tuple[bool, str]:
        payload = {
            "model": self.settings.model_name,
            "input": {
                "image_url": "https://example.invalid/avatar.jpg",
                "audio_url": "https://example.invalid/audio.wav",
            },
            "parameters": {"resolution": self.settings.resolution},
        }
        response = self.session.post(
            self._url("/api/v1/services/aigc/image2video/video-synthesis"),
            headers=self._headers(async_task=True, oss_resolve=True),
            json=payload,
            timeout=self.settings.request_timeout_s,
        )
        if response.status_code in {401, 403}:
            return False, f"鉴权或权限失败（HTTP {response.status_code}）"
        return True, f"接口可达（HTTP {response.status_code}）"

    @staticmethod
    def _extract_audio_url(payload: dict[str, Any]) -> str:
        output = payload.get("output") or {}
        audio = output.get("audio") if isinstance(output.get("audio"), dict) else {}
        candidates = [
            audio.get("url"),
            audio.get("audio_url"),
            output.get("audio_url"),
            output.get("url"),
            output.get("speech_url"),
        ]
        return next((str(item).strip() for item in candidates if item), "")

    @staticmethod
    def _extract_video_url(output: dict[str, Any]) -> str:
        results = output.get("results")
        if isinstance(results, list) and results:
            first = results[0] if isinstance(results[0], dict) else {}
            candidates = [first.get("video_url"), first.get("url")]
        elif isinstance(results, dict):
            candidates = [results.get("video_url"), results.get("url")]
        else:
            candidates = []
        candidates.extend([output.get("video_url"), output.get("url")])
        return next((str(item).strip() for item in candidates if item), "")

    @staticmethod
    def _raise_for_response(response, context: str) -> None:
        try:
            response.raise_for_status()
        except requests.RequestException as exc:
            message = getattr(response, "text", "") or str(exc)
            raise DigitalHumanVideoError(f"{context}: {message[:240]}", 502) from exc
