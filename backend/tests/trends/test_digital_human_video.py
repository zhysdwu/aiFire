from django.conf import settings
from django.db import IntegrityError, models, transaction
from django.test import override_settings
import pytest
from rest_framework.test import APIClient

from apps.trends.models import DigitalHumanEngineConfig
from apps.trends.services.digital_human_video_service import (
    build_srt_content,
    DigitalHumanVideoError,
    find_ffmpeg_binary,
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


def test_find_ffmpeg_binary_uses_local_tools_fallback(tmp_path, monkeypatch):
    local_tools = tmp_path / "tools" / "ffmpeg" / "unzipped" / "build" / "bin"
    local_tools.mkdir(parents=True)
    ffmpeg = local_tools / "ffmpeg.exe"
    ffmpeg.write_text("fake", encoding="utf-8")

    monkeypatch.delenv("FFMPEG_BINARY", raising=False)
    monkeypatch.setattr("apps.trends.services.digital_human_video_service.shutil.which", lambda name: None)
    monkeypatch.setattr(
        "apps.trends.services.digital_human_video_service.local_ffmpeg_roots",
        lambda: [tmp_path / "tools" / "ffmpeg"],
    )

    assert find_ffmpeg_binary() == str(ffmpeg)


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


@pytest.mark.django_db
def test_digital_human_video_create_rejects_short_script():
    client = APIClient()
    response = client.post(
        "/api/digital-human/videos/",
        {"script": "a", "audio_mode": "default", "video_mode": "default"},
        format="multipart",
    )
    assert response.status_code == 400
    assert "至少 2 个字" in response.data["message"]


@pytest.mark.django_db
def test_digital_human_video_create_success(monkeypatch):
    client = APIClient()

    def fake_generate(**kwargs):
        return {
            "job_id": "job-123",
            "status": "success",
            "engine": "ffmpeg_composite",
            "video_url": "/media/digital_human/outputs/job-123.mp4",
            "download_url": "/api/digital-human/videos/job-123/download/",
            "message": "生成完成",
        }

    monkeypatch.setattr("apps.trends.api.digital_human_views.generate_digital_human_video", fake_generate)
    response = client.post(
        "/api/digital-human/videos/",
        {"script": "生成一条视频", "audio_mode": "default", "video_mode": "default"},
        format="multipart",
    )
    assert response.status_code == 200
    assert response.data["status"] == "success"
    assert response.data["download_url"] == "/api/digital-human/videos/job-123/download/"


@pytest.mark.django_db
def test_digital_human_video_download_returns_file(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    output_dir = tmp_path / "digital_human" / "outputs"
    output_dir.mkdir(parents=True)
    output_path = output_dir / "job-123.mp4"
    output_path.write_bytes(b"fake mp4")

    client = APIClient()
    response = client.get("/api/digital-human/videos/job-123/download/")

    assert response.status_code == 200
    assert response["Content-Type"] == "video/mp4"


@pytest.mark.django_db
def test_digital_human_engine_default_is_unique():
    first = DigitalHumanEngineConfig.objects.create(
        name="Local A",
        engine_type=DigitalHumanEngineConfig.EngineType.LOCAL_FFMPEG,
        is_enabled=True,
        is_default=True,
    )
    second = DigitalHumanEngineConfig.objects.create(
        name="Local B",
        engine_type=DigitalHumanEngineConfig.EngineType.LOCAL_FFMPEG,
        is_enabled=True,
        is_default=True,
    )

    first.refresh_from_db()
    second.refresh_from_db()
    assert first.is_default is False
    assert second.is_default is True


@pytest.mark.django_db
def test_digital_human_engine_str_returns_name():
    config = DigitalHumanEngineConfig.objects.create(name="Jimeng visual")

    assert str(config) == "Jimeng visual"


@pytest.mark.django_db
def test_digital_human_engine_default_is_enforced_at_database_level():
    DigitalHumanEngineConfig.objects.create(
        name="Local A",
        engine_type=DigitalHumanEngineConfig.EngineType.LOCAL_FFMPEG,
        is_enabled=True,
        is_default=True,
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        DigitalHumanEngineConfig.objects.bulk_create(
            [
                DigitalHumanEngineConfig(
                    name="Local B",
                    engine_type=DigitalHumanEngineConfig.EngineType.LOCAL_FFMPEG,
                    is_enabled=True,
                    is_default=True,
                )
            ]
        )


def test_digital_human_engine_default_unique_constraint_uses_generated_key():
    field = DigitalHumanEngineConfig._meta.get_field("default_unique_key")
    constraint = next(
        item
        for item in DigitalHumanEngineConfig._meta.constraints
        if item.name == "unique_default_digital_human_engine_config"
    )

    assert isinstance(field, models.GeneratedField)
    assert field.db_persist is True
    assert constraint.fields == ("default_unique_key",)
    assert constraint.condition is None
