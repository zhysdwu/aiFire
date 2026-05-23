from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from django.conf import settings


AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm"}
MAX_UPLOAD_BYTES = 100 * 1024 * 1024


@dataclass
class DigitalHumanVideoError(Exception):
    message: str
    status_code: int = 400


@dataclass(frozen=True)
class GenerationPaths:
    job_id: str
    output_path: Path
    subtitle_path: Path
    upload_dir: Path


@dataclass(frozen=True)
class GenerationResult:
    job_id: str
    status: str
    engine: str
    video_url: str
    download_url: str
    message: str


def digital_human_media_root() -> Path:
    return Path(settings.MEDIA_ROOT) / "digital_human"


def validate_generation_request(*, script: str, audio_mode: str, video_mode: str, files) -> None:
    if len((script or "").strip()) < 2:
        raise DigitalHumanVideoError("请输入至少 2 个字的口播脚本", 400)
    if audio_mode not in {"default", "upload"}:
        raise DigitalHumanVideoError("音频来源必须是 default 或 upload", 400)
    if video_mode not in {"default", "upload"}:
        raise DigitalHumanVideoError("视频来源必须是 default 或 upload", 400)
    if audio_mode == "upload" and not files.get("audio_file"):
        raise DigitalHumanVideoError("请上传音频文件", 400)
    if video_mode == "upload" and not files.get("video_file"):
        raise DigitalHumanVideoError("请上传视频文件", 400)
