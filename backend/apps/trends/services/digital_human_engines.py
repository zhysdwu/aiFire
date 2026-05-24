from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Protocol

from apps.trends.models import DigitalHumanEngineConfig
from apps.trends.services.digital_human_video_service import DigitalHumanVideoError


ENGINE_LABELS = {
    DigitalHumanEngineConfig.EngineType.LOCAL_FFMPEG: "Local composite",
    DigitalHumanEngineConfig.EngineType.JIMENG_VISUAL: "Jimeng visual video",
    DigitalHumanEngineConfig.EngineType.TALKING_AVATAR: "Talking avatar",
    DigitalHumanEngineConfig.EngineType.ALIBABA_WANXIANG: "Alibaba Wanxiang digital human",
}

SUBTITLE_LABELS = {
    DigitalHumanEngineConfig.SubtitleMode.NONE: "No subtitles",
    DigitalHumanEngineConfig.SubtitleMode.ZH: "Chinese subtitles",
    DigitalHumanEngineConfig.SubtitleMode.ZH_EN: "Chinese and English subtitles",
}


@dataclass(frozen=True)
class ImplicitLocalEngineConfig:
    id: None = None
    name: str = "Local digital human fallback"
    engine_type: str = DigitalHumanEngineConfig.EngineType.LOCAL_FFMPEG
    subtitle_mode: str = DigitalHumanEngineConfig.SubtitleMode.ZH_EN
    is_default: bool = True
    is_enabled: bool = True
    api_key: str = ""
    api_base_url: str = ""
    model_name: str = ""
    avatar_id: str = ""
    voice_id: str = ""
    default_prompt: str = ""
    extra_config: dict = field(default_factory=dict)


def enabled_engine_configs():
    return DigitalHumanEngineConfig.objects.filter(is_enabled=True).order_by("-is_default", "name")


def default_engine_config():
    config = enabled_engine_configs().filter(is_default=True).first()
    if config:
        return config
    config = enabled_engine_configs().first()
    if config:
        return config
    return ImplicitLocalEngineConfig()


def resolve_engine_config(config_id):
    if config_id is None or (isinstance(config_id, str) and not config_id.strip()):
        return default_engine_config()
    try:
        config_id_int = int(config_id)
    except (TypeError, ValueError):
        raise DigitalHumanVideoError("数字人配置无效", 400)
    config = DigitalHumanEngineConfig.objects.filter(id=config_id_int, is_enabled=True).first()
    if not config:
        raise DigitalHumanVideoError("数字人配置不存在或已停用", 400)
    return config


def engine_config_to_public_dict(config) -> dict:
    return {
        "id": config.id,
        "name": config.name,
        "engine_type": config.engine_type,
        "engine_label": ENGINE_LABELS.get(config.engine_type, config.engine_type),
        "subtitle_mode": config.subtitle_mode,
        "subtitle_label": SUBTITLE_LABELS.get(config.subtitle_mode, config.subtitle_mode),
        "is_default": bool(config.is_default),
    }


class DigitalHumanEngineAdapter(Protocol):
    def generate(self, *, script: str, audio_mode: str, video_mode: str, files, config, api_key_override: str = "") -> dict:
        ...


class LocalFfmpegEngineAdapter:
    def generate(self, *, script: str, audio_mode: str, video_mode: str, files, config, api_key_override: str = "") -> dict:
        from apps.trends.services.digital_human_video_service import generate_local_ffmpeg_video

        return generate_local_ffmpeg_video(
            script=script,
            audio_mode=audio_mode,
            video_mode=video_mode,
            files=files,
            engine_config=config,
        )


class JimengVisualEngineAdapter:
    def generate(self, *, script: str, audio_mode: str, video_mode: str, files, config, api_key_override: str = "") -> dict:
        payload = {
            "status": "failed",
            "engine": DigitalHumanEngineConfig.EngineType.JIMENG_VISUAL,
            "engine_config": engine_config_to_public_dict(config),
        }
        if not (config.api_key or "").strip():
            return {**payload, "message": "Jimeng visual API Key is required."}
        return {**payload, "message": "Jimeng visual engine is not integrated yet."}


class TalkingAvatarEngineAdapter:
    def generate(self, *, script: str, audio_mode: str, video_mode: str, files, config, api_key_override: str = "") -> dict:
        payload = {
            "status": "failed",
            "engine": DigitalHumanEngineConfig.EngineType.TALKING_AVATAR,
            "engine_config": engine_config_to_public_dict(config),
        }
        if not (config.api_key or "").strip():
            return {**payload, "message": "Talking avatar API Key is required."}
        return {**payload, "message": "Talking avatar engine is not integrated yet."}


class AlibabaWanxiangEngineAdapter:
    def generate(self, *, script: str, audio_mode: str, video_mode: str, files, config, api_key_override: str = "") -> dict:
        from apps.trends.services.alibaba_wanxiang_client import (
            AlibabaWanxiangClient,
            settings_from_engine_config,
        )
        from apps.trends.services.digital_human_video_service import (
            build_paths,
            default_video_path,
            ensure_default_assets,
            ensure_dirs,
            extract_avatar_frame,
            find_ffmpeg_binary,
            media_url_for_output,
            resolve_audio_path,
            resolve_video_path,
            result_with_engine_config,
        )

        payload = {
            "status": "failed",
            "engine": DigitalHumanEngineConfig.EngineType.ALIBABA_WANXIANG,
            "engine_config": engine_config_to_public_dict(config),
        }
        effective_api_key = (api_key_override or config.api_key or "").strip()
        if not effective_api_key:
            return {**payload, "message": "Alibaba Wanxiang API Key is required."}
        runtime_config = SimpleNamespace(
            api_key=effective_api_key,
            api_base_url=config.api_base_url,
            model_name=config.model_name,
            avatar_id=config.avatar_id,
            voice_id=config.voice_id,
            extra_config=config.extra_config,
        )

        extra_config = config.extra_config if isinstance(config.extra_config, dict) else {}
        configured_avatar_url = (config.avatar_id or extra_config.get("avatar_image_url") or "").strip()

        import uuid

        job_id = str(uuid.uuid4())
        paths = build_paths(job_id)
        ensure_dirs(paths)
        avatar_image_path = None

        try:
            if video_mode == "upload" or not configured_avatar_url:
                ffmpeg = find_ffmpeg_binary()
                if not ffmpeg:
                    return {**payload, "message": "生成失败：未找到 ffmpeg，无法为阿里万相提取数字人人像首帧"}
                ensure_default_assets(ffmpeg)
                video_path = default_video_path() if video_mode == "default" else resolve_video_path(video_mode, files, paths)
                avatar_image_path = paths.upload_dir / "avatar.jpg"
                extract_avatar_frame(ffmpeg, video_path, avatar_image_path)
            audio_path = resolve_audio_path(audio_mode, files, paths) if audio_mode == "upload" else None
            client = AlibabaWanxiangClient(settings_from_engine_config(runtime_config))
            generation = client.generate_video(
                script=script,
                audio_mode=audio_mode,
                audio_path=audio_path,
                avatar_image_path=avatar_image_path,
                avatar_image_url="" if video_mode == "upload" else configured_avatar_url,
                output_path=paths.output_path,
            )
        except DigitalHumanVideoError as exc:
            return {**payload, "message": exc.message}
        except Exception as exc:
            return {**payload, "message": f"Alibaba Wanxiang generation failed: {str(exc)[:240]}"}

        result = {
            "job_id": job_id,
            "status": "success",
            "engine": DigitalHumanEngineConfig.EngineType.ALIBABA_WANXIANG,
            "video_url": media_url_for_output(job_id),
            "download_url": f"/api/digital-human/videos/{job_id}/download/",
            "message": "Alibaba Wanxiang video generated successfully.",
            "provider_task_id": generation.get("task_id", ""),
            "provider_video_url": generation.get("source_video_url", ""),
        }
        return result_with_engine_config(
            result,
            engine=DigitalHumanEngineConfig.EngineType.ALIBABA_WANXIANG,
            engine_config=config,
        )


ADAPTERS: dict[str, DigitalHumanEngineAdapter] = {
    DigitalHumanEngineConfig.EngineType.LOCAL_FFMPEG: LocalFfmpegEngineAdapter(),
    DigitalHumanEngineConfig.EngineType.JIMENG_VISUAL: JimengVisualEngineAdapter(),
    DigitalHumanEngineConfig.EngineType.TALKING_AVATAR: TalkingAvatarEngineAdapter(),
    DigitalHumanEngineConfig.EngineType.ALIBABA_WANXIANG: AlibabaWanxiangEngineAdapter(),
}


def get_engine_adapter(engine_type: str) -> DigitalHumanEngineAdapter:
    adapter = ADAPTERS.get(engine_type)
    if not adapter:
        raise DigitalHumanVideoError("当前数字人引擎尚未接入", 500)
    return adapter


def public_engine_config_payload() -> dict:
    configs = [engine_config_to_public_dict(config) for config in enabled_engine_configs()]
    if not configs:
        fallback = engine_config_to_public_dict(ImplicitLocalEngineConfig())
        return {
            "configs": [fallback],
            "default_config_id": None,
        }
    default_config = next((item for item in configs if item["is_default"]), configs[0] if configs else None)
    return {
        "configs": configs,
        "default_config_id": default_config["id"] if default_config else None,
    }
