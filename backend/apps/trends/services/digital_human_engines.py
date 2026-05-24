from __future__ import annotations

from dataclasses import dataclass, field

from apps.trends.models import DigitalHumanEngineConfig
from apps.trends.services.digital_human_video_service import DigitalHumanVideoError


ENGINE_LABELS = {
    DigitalHumanEngineConfig.EngineType.LOCAL_FFMPEG: "Local composite",
    DigitalHumanEngineConfig.EngineType.JIMENG_VISUAL: "Jimeng visual video",
    DigitalHumanEngineConfig.EngineType.TALKING_AVATAR: "Talking avatar",
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
