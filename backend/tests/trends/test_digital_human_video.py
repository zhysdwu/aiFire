from django.conf import settings
from django.test import override_settings
import pytest

from apps.trends.services.digital_human_video_service import (
    build_srt_content,
    DigitalHumanVideoError,
    generate_digital_human_video,
    validate_generation_request,
)


def test_media_settings_are_configured():
    assert settings.MEDIA_URL == "/media/"
    assert settings.MEDIA_ROOT.name == "media"


def test_validate_generation_request_rejects_short_script():
    with pytest.raises(DigitalHumanVideoError) as exc:
        validate_generation_request(script="a", audio_mode="default", video_mode="default", files={})
    assert exc.value.status_code == 400
    assert "至少 2 个字" in exc.value.message


def test_validate_generation_request_requires_upload_audio_file():
    with pytest.raises(DigitalHumanVideoError) as exc:
        validate_generation_request(script="生成一条视频", audio_mode="upload", video_mode="default", files={})
    assert exc.value.status_code == 400
    assert "请上传音频文件" in exc.value.message


def test_validate_generation_request_requires_upload_video_file():
    with pytest.raises(DigitalHumanVideoError) as exc:
        validate_generation_request(script="生成一条视频", audio_mode="default", video_mode="upload", files={})
    assert exc.value.status_code == 400
    assert "请上传视频文件" in exc.value.message


def test_build_srt_content_escapes_blank_script():
    content = build_srt_content("第一句\n\n第二句")
    assert "1" in content
    assert "00:00:00,000 --> 00:00:08,000" in content
    assert "第一句 第二句" in content


@override_settings(MEDIA_URL="/media/")
def test_generate_digital_human_video_returns_failed_when_ffmpeg_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "apps.trends.services.digital_human_video_service.digital_human_media_root",
        lambda: tmp_path / "digital_human",
    )
    monkeypatch.setattr("apps.trends.services.digital_human_video_service.find_ffmpeg_binary", lambda: None)

    result = generate_digital_human_video(
        script="生成一条默认视频",
        audio_mode="default",
        video_mode="default",
        files={},
    )

    assert result["status"] == "failed"
    assert "ffmpeg" in result["message"].lower()
