from __future__ import annotations

import logging
import os
from dataclasses import dataclass

import requests


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LiveTalkingConfig:
    endpoint: str
    timeout_s: int = 5


class LiveTalkingClient:
    def __init__(self, config: LiveTalkingConfig):
        self.config = config

    @classmethod
    def from_env(cls) -> "LiveTalkingClient":
        endpoint = os.getenv("LIVETALKING_ENDPOINT", "").strip()
        if not endpoint:
            raise RuntimeError("Missing LIVETALKING_ENDPOINT")
        return cls(LiveTalkingConfig(endpoint=endpoint))

    def speak(self, text: str, trace_id: str) -> dict:
        payload = {"text": text, "trace_id": trace_id}
        response = requests.post(self.config.endpoint, json=payload, timeout=self.config.timeout_s)
        response.raise_for_status()
        return {"status": "queued", "message": "livetalking accepted"}


def trigger_livetalking(answer: str, trace_id: str) -> dict:
    try:
        client = LiveTalkingClient.from_env()
    except RuntimeError as exc:
        logger.warning("LiveTalking config missing: %s", exc)
        return {"status": "skipped", "message": "livetalking 未配置 (缺少 LIVETALKING_ENDPOINT 环境变量)"}
    except Exception as exc:
        logger.warning("LiveTalking client init failed: %s", exc, exc_info=True)
        return {"status": "failed", "message": f"livetalking 初始化失败: {exc}"}

    try:
        return client.speak(answer, trace_id)
    except requests.ConnectionError as exc:
        logger.warning("LiveTalking unreachable at %s: %s", client.config.endpoint, exc)
        return {"status": "failed", "message": f"livetalking 服务不可达 ({client.config.endpoint})"}
    except requests.Timeout as exc:
        logger.warning("LiveTalking timeout (%ds): %s", client.config.timeout_s, exc)
        return {"status": "failed", "message": f"livetalking 请求超时 (>{client.config.timeout_s}s)"}
    except requests.RequestException as exc:
        logger.warning("LiveTalking request failed: %s", exc, exc_info=True)
        return {"status": "failed", "message": f"livetalking 请求异常: {exc}"}
    except Exception as exc:
        logger.warning("LiveTalking trigger failed: %s", exc, exc_info=True)
        return {"status": "failed", "message": f"livetalking 异常: {exc}"}
