from django.conf import settings
import pytest

from apps.trends.services.digital_human_video_service import (
    DigitalHumanVideoError,
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
