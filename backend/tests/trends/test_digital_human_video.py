from django.conf import settings
from django.db import IntegrityError, models, transaction
from django.test import override_settings
import pytest
from rest_framework.test import APIClient

from apps.trends.models import DigitalHumanEngineConfig
from apps.trends.services.digital_human_engines import (
    engine_config_to_public_dict,
    resolve_engine_config,
)
from apps.trends.services.digital_human_video_service import (
    build_bilingual_srt_content,
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


def test_build_bilingual_srt_content_contains_chinese_and_english_lines():
    content = build_bilingual_srt_content("你好世界", "Hello world")

    assert "你好世界" in content
    assert "Hello world" in content
    assert "00:00:00,000 --> 00:00:08,000" in content


@pytest.mark.django_db
def test_local_generation_skips_subtitle_filter_when_subtitle_mode_none(tmp_path, monkeypatch):
    config = DigitalHumanEngineConfig.objects.create(
        name="No subtitle local",
        engine_type=DigitalHumanEngineConfig.EngineType.LOCAL_FFMPEG,
        is_enabled=True,
        is_default=True,
        subtitle_mode=DigitalHumanEngineConfig.SubtitleMode.NONE,
    )
    calls = {}

    monkeypatch.setattr(
        "apps.trends.services.digital_human_video_service.digital_human_media_root",
        lambda: tmp_path / "digital_human",
    )
    monkeypatch.setattr("apps.trends.services.digital_human_video_service.find_ffmpeg_binary", lambda: "ffmpeg")
    monkeypatch.setattr("apps.trends.services.digital_human_video_service.ensure_default_assets", lambda ffmpeg: None)
    monkeypatch.setattr(
        "apps.trends.services.digital_human_video_service.run_ffmpeg_composite",
        lambda *args: calls.setdefault("subtitle_path", args[3]),
    )

    result = generate_digital_human_video(
        script="生成一条默认视频",
        audio_mode="default",
        video_mode="default",
        files={},
        config_id=str(config.id),
    )

    assert result["status"] == "success"
    assert calls["subtitle_path"] is None


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
@pytest.mark.django_db
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
def test_generation_with_jimeng_config_without_api_key_returns_clear_error():
    config = DigitalHumanEngineConfig.objects.create(
        name="Jimeng visual",
        engine_type=DigitalHumanEngineConfig.EngineType.JIMENG_VISUAL,
        is_enabled=True,
        is_default=True,
    )

    result = generate_digital_human_video(
        script="生成一条默认视频",
        audio_mode="default",
        video_mode="default",
        files={},
        config_id=str(config.id),
    )

    assert result["status"] == "failed"
    assert "API Key" in result["message"]
    assert result["engine"] == "jimeng_visual"
    assert result["engine_config"]["id"] == config.id


@pytest.mark.django_db
def test_generation_without_config_id_uses_enabled_default_config():
    config = DigitalHumanEngineConfig.objects.create(
        name="Jimeng default",
        engine_type=DigitalHumanEngineConfig.EngineType.JIMENG_VISUAL,
        is_enabled=True,
        is_default=True,
    )

    result = generate_digital_human_video(
        script="生成一条默认视频",
        audio_mode="default",
        video_mode="default",
        files={},
    )

    assert result["status"] == "failed"
    assert "API Key" in result["message"]
    assert result["engine"] == "jimeng_visual"
    assert result["engine_config"]["id"] == config.id


@pytest.mark.django_db
def test_generation_response_includes_local_engine_config(monkeypatch):
    config = DigitalHumanEngineConfig.objects.create(
        name="Local composite",
        engine_type=DigitalHumanEngineConfig.EngineType.LOCAL_FFMPEG,
        is_enabled=True,
        is_default=True,
    )
    monkeypatch.setattr("apps.trends.services.digital_human_video_service.find_ffmpeg_binary", lambda: None)

    result = generate_digital_human_video(
        script="生成一条默认视频",
        audio_mode="default",
        video_mode="default",
        files={},
        config_id=str(config.id),
    )

    assert result["status"] == "failed"
    assert result["engine"] == "ffmpeg_composite"
    assert result["engine_config"]["id"] == config.id
    assert result["engine_config"]["name"] == "Local composite"


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


@pytest.mark.django_db
def test_engine_config_list_hides_disabled_and_api_key():
    enabled = DigitalHumanEngineConfig.objects.create(
        name="Enabled local",
        engine_type=DigitalHumanEngineConfig.EngineType.LOCAL_FFMPEG,
        is_enabled=True,
        is_default=True,
        api_key="secret-key",
    )
    DigitalHumanEngineConfig.objects.create(
        name="Disabled Jimeng",
        engine_type=DigitalHumanEngineConfig.EngineType.JIMENG_VISUAL,
        is_enabled=False,
    )

    client = APIClient()
    response = client.get("/api/digital-human/video-configs/")

    assert response.status_code == 200
    assert response.data["default_config_id"] == enabled.id
    assert len(response.data["configs"]) == 1
    assert response.data["configs"][0]["name"] == "Enabled local"
    assert "api_key" not in response.data["configs"][0]


@pytest.mark.django_db
def test_resolve_engine_config_rejects_disabled_config():
    config = DigitalHumanEngineConfig.objects.create(name="Disabled", is_enabled=False)

    with pytest.raises(DigitalHumanVideoError) as exc:
        resolve_engine_config(str(config.id))

    assert exc.value.status_code == 400
    assert "配置" in exc.value.message


@pytest.mark.django_db
def test_resolve_engine_config_returns_implicit_local_fallback_when_empty():
    config = resolve_engine_config("")

    assert config.id is None
    assert config.name == "Local digital human fallback"
    assert config.engine_type == DigitalHumanEngineConfig.EngineType.LOCAL_FFMPEG
    assert config.subtitle_mode == DigitalHumanEngineConfig.SubtitleMode.ZH_EN


@pytest.mark.django_db
def test_resolve_engine_config_rejects_zero_config_id():
    with pytest.raises(DigitalHumanVideoError) as exc:
        resolve_engine_config(0)

    assert exc.value.status_code == 400
    assert "配置" in exc.value.message


@pytest.mark.django_db
def test_engine_config_list_includes_implicit_local_fallback_when_empty():
    client = APIClient()
    response = client.get("/api/digital-human/video-configs/")

    assert response.status_code == 200
    assert response.data["default_config_id"] is None
    assert response.data["configs"] == [
        {
            "id": None,
            "name": "Local digital human fallback",
            "engine_type": DigitalHumanEngineConfig.EngineType.LOCAL_FFMPEG,
            "engine_label": "Local composite",
            "subtitle_mode": DigitalHumanEngineConfig.SubtitleMode.ZH_EN,
            "subtitle_label": "Chinese and English subtitles",
            "is_default": True,
        }
    ]


@pytest.mark.django_db
def test_engine_config_to_public_dict_has_labels():
    config = DigitalHumanEngineConfig.objects.create(
        name="Jimeng visual",
        engine_type=DigitalHumanEngineConfig.EngineType.JIMENG_VISUAL,
        subtitle_mode=DigitalHumanEngineConfig.SubtitleMode.ZH_EN,
        is_default=True,
    )

    data = engine_config_to_public_dict(config)

    assert data["id"] == config.id
    assert data["engine_label"] == "Jimeng visual video"
    assert data["subtitle_label"] == "Chinese and English subtitles"
    assert data["is_default"] is True
    assert "api_key" not in data


@pytest.mark.django_db
def test_alibaba_wanxiang_engine_config_has_public_label():
    config = DigitalHumanEngineConfig.objects.create(
        name="Alibaba Wanxiang",
        engine_type=DigitalHumanEngineConfig.EngineType.ALIBABA_WANXIANG,
        subtitle_mode=DigitalHumanEngineConfig.SubtitleMode.ZH_EN,
        is_default=True,
        api_key="secret-key",
    )

    data = engine_config_to_public_dict(config)

    assert data["engine_type"] == "alibaba_wanxiang"
    assert data["engine_label"] == "Alibaba Wanxiang digital human"
    assert data["subtitle_label"] == "Chinese and English subtitles"
    assert "api_key" not in data


@pytest.mark.django_db
def test_generation_with_alibaba_wanxiang_config_without_api_key_returns_clear_error():
    config = DigitalHumanEngineConfig.objects.create(
        name="Alibaba Wanxiang",
        engine_type=DigitalHumanEngineConfig.EngineType.ALIBABA_WANXIANG,
        is_enabled=True,
        is_default=True,
    )

    result = generate_digital_human_video(
        script="Generate a digital human video",
        audio_mode="default",
        video_mode="default",
        files={},
        config_id=str(config.id),
    )

    assert result["status"] == "failed"
    assert "Alibaba Wanxiang API Key" in result["message"]
    assert result["engine"] == "alibaba_wanxiang"
    assert result["engine_config"]["id"] == config.id


@pytest.mark.django_db
def test_alibaba_wanxiang_generation_uses_tts_avatar_frame_and_downloads_video(tmp_path, monkeypatch):
    config = DigitalHumanEngineConfig.objects.create(
        name="Alibaba Wanxiang",
        engine_type=DigitalHumanEngineConfig.EngineType.ALIBABA_WANXIANG,
        is_enabled=True,
        is_default=True,
        api_key="sk-test",
        voice_id="longanyang",
        extra_config={"poll_timeout_s": 1, "poll_interval_s": 0, "resolution": "480P"},
    )
    media_root = tmp_path / "digital_human"
    default_video = media_root / "defaults" / "default_video.mp4"
    default_video.parent.mkdir(parents=True)
    default_video.write_bytes(b"fake-video")
    captured = {}

    class FakeWanxiangClient:
        def __init__(self, settings, session=None, sleep_func=None):
            captured["settings"] = settings

        def generate_video(self, *, script, audio_mode, audio_path, avatar_image_path=None, avatar_image_url="", output_path):
            captured["script"] = script
            captured["audio_mode"] = audio_mode
            captured["audio_path"] = audio_path
            captured["avatar_image_path"] = avatar_image_path
            captured["avatar_image_url"] = avatar_image_url
            output_path.write_bytes(b"generated-mp4")
            return {"task_id": "task-123", "source_video_url": "https://example.test/result.mp4"}

    def fake_extract_avatar_frame(ffmpeg, video_path, image_path):
        captured["ffmpeg"] = ffmpeg
        captured["video_path"] = video_path
        image_path.write_bytes(b"avatar")
        return image_path

    monkeypatch.setattr(
        "apps.trends.services.digital_human_video_service.digital_human_media_root",
        lambda: media_root,
    )
    monkeypatch.setattr("apps.trends.services.digital_human_video_service.find_ffmpeg_binary", lambda: "ffmpeg")
    monkeypatch.setattr("apps.trends.services.digital_human_video_service.ensure_default_assets", lambda ffmpeg: None)
    monkeypatch.setattr(
        "apps.trends.services.digital_human_video_service.extract_avatar_frame",
        fake_extract_avatar_frame,
    )
    monkeypatch.setattr(
        "apps.trends.services.alibaba_wanxiang_client.AlibabaWanxiangClient",
        FakeWanxiangClient,
    )

    result = generate_digital_human_video(
        script="Generate a digital human video",
        audio_mode="default",
        video_mode="default",
        files={},
        config_id=str(config.id),
    )

    assert result["status"] == "success"
    assert result["engine"] == "alibaba_wanxiang"
    assert result["engine_config"]["id"] == config.id
    assert result["video_url"].startswith("/media/digital_human/outputs/")
    assert result["download_url"].startswith("/api/digital-human/videos/")
    assert captured["settings"].api_key == "sk-test"
    assert captured["settings"].model_name == "wan2.2-s2v"
    assert captured["settings"].voice == "longanyang"
    assert captured["settings"].resolution == "480P"
    assert captured["audio_mode"] == "default"
    assert captured["avatar_image_path"].read_bytes() == b"avatar"
    assert captured["video_path"] == default_video


@pytest.mark.django_db
def test_alibaba_wanxiang_generation_uses_configured_avatar_url_without_ffmpeg(tmp_path, monkeypatch):
    config = DigitalHumanEngineConfig.objects.create(
        name="Alibaba Wanxiang URL avatar",
        engine_type=DigitalHumanEngineConfig.EngineType.ALIBABA_WANXIANG,
        is_enabled=True,
        is_default=True,
        api_key="sk-test",
        avatar_id="https://cdn.example.test/avatar.png",
    )
    media_root = tmp_path / "digital_human"
    captured = {}

    class FakeWanxiangClient:
        def __init__(self, settings, session=None, sleep_func=None):
            captured["settings"] = settings

        def generate_video(self, *, script, audio_mode, audio_path, avatar_image_path=None, avatar_image_url=None, output_path):
            captured["avatar_image_path"] = avatar_image_path
            captured["avatar_image_url"] = avatar_image_url
            output_path.write_bytes(b"generated-mp4")
            return {"task_id": "task-456", "source_video_url": "https://example.test/result.mp4"}

    monkeypatch.setattr(
        "apps.trends.services.digital_human_video_service.digital_human_media_root",
        lambda: media_root,
    )
    monkeypatch.setattr("apps.trends.services.digital_human_video_service.find_ffmpeg_binary", lambda: None)
    monkeypatch.setattr(
        "apps.trends.services.alibaba_wanxiang_client.AlibabaWanxiangClient",
        FakeWanxiangClient,
    )

    result = generate_digital_human_video(
        script="Generate a digital human video",
        audio_mode="default",
        video_mode="default",
        files={},
        config_id=str(config.id),
    )

    assert result["status"] == "success"
    assert result["engine"] == "alibaba_wanxiang"
    assert captured["avatar_image_url"] == "https://cdn.example.test/avatar.png"
    assert captured["avatar_image_path"] is None


def test_alibaba_wanxiang_client_submits_polls_and_downloads(tmp_path):
    from apps.trends.services.alibaba_wanxiang_client import AlibabaWanxiangClient, AlibabaWanxiangSettings

    output_path = tmp_path / "output.mp4"
    avatar_path = tmp_path / "avatar.jpg"
    audio_path = tmp_path / "audio.wav"
    avatar_path.write_bytes(b"avatar")
    audio_path.write_bytes(b"audio")
    calls = []

    class FakeResponse:
        def __init__(self, payload=None, content=b"", status_code=200):
            self.payload = payload or {}
            self.content = content
            self.status_code = status_code
            self.text = str(self.payload)

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(self.text)

        def json(self):
            return self.payload

        def iter_content(self, chunk_size=1024 * 1024):
            yield self.content

    class FakeSession:
        def get(self, url, **kwargs):
            calls.append(("GET", url, kwargs))
            if url.endswith("/api/v1/uploads"):
                return FakeResponse(
                    {
                        "data": {
                            "upload_dir": "dashscope-instant/test",
                            "oss_access_key_id": "ak",
                            "signature": "sig",
                            "policy": "policy",
                            "x_oss_object_acl": "private",
                            "x_oss_forbid_overwrite": "true",
                            "upload_host": "https://upload.example.test",
                        }
                    }
                )
            if url.endswith("/api/v1/tasks/task-123"):
                return FakeResponse({"output": {"task_status": "SUCCEEDED", "results": {"video_url": "https://result.example.test/video.mp4"}}})
            if url == "https://result.example.test/video.mp4":
                return FakeResponse(content=b"mp4-data")
            raise AssertionError(f"unexpected GET {url}")

        def post(self, url, **kwargs):
            calls.append(("POST", url, kwargs))
            if url == "https://upload.example.test":
                return FakeResponse()
            if url.endswith("/api/v1/services/aigc/image2video/video-synthesis"):
                return FakeResponse({"output": {"task_id": "task-123", "task_status": "PENDING"}})
            raise AssertionError(f"unexpected POST {url}")

    client = AlibabaWanxiangClient(
        AlibabaWanxiangSettings(api_key="sk-test", poll_interval_s=0, poll_timeout_s=1),
        session=FakeSession(),
        sleep_func=lambda seconds: None,
    )

    result = client.generate_video(
        script="Generate a digital human video",
        audio_mode="upload",
        audio_path=audio_path,
        avatar_image_path=avatar_path,
        output_path=output_path,
    )

    assert result["task_id"] == "task-123"
    assert result["source_video_url"] == "https://result.example.test/video.mp4"
    assert output_path.read_bytes() == b"mp4-data"
    task_posts = [call for call in calls if call[0] == "POST" and call[1].endswith("/video-synthesis")]
    assert task_posts[0][2]["headers"]["X-DashScope-Async"] == "enable"
    assert task_posts[0][2]["headers"]["X-DashScope-OssResourceResolve"] == "enable"
    assert task_posts[0][1] == "https://dashscope.aliyuncs.com/api/v1/services/aigc/image2video/video-synthesis"
    assert task_posts[0][2]["json"]["model"] == "wan2.2-s2v"
    assert task_posts[0][2]["json"]["parameters"]["resolution"] == "480P"


def test_alibaba_wanxiang_client_uses_qwen_http_tts_for_default_audio():
    from apps.trends.services.alibaba_wanxiang_client import AlibabaWanxiangClient, AlibabaWanxiangSettings

    calls = []

    class FakeResponse:
        text = "{}"

        def raise_for_status(self):
            return None

        def json(self):
            return {"output": {"audio": {"url": "https://audio.example.test/speech.wav"}}}

    class FakeSession:
        def post(self, url, **kwargs):
            calls.append(("POST", url, kwargs))
            return FakeResponse()

    client = AlibabaWanxiangClient(
        AlibabaWanxiangSettings(api_key="sk-test", tts_model="qwen3-tts-flash", voice="Cherry"),
        session=FakeSession(),
    )

    audio_url = client.synthesize_tts("你好，欢迎观看今天的热点解读。")

    assert audio_url == "https://audio.example.test/speech.wav"
    assert calls[0][1] == "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
    assert calls[0][2]["json"] == {
        "model": "qwen3-tts-flash",
        "input": {
            "text": "你好，欢迎观看今天的热点解读。",
            "voice": "Cherry",
            "language_type": "Chinese",
        },
    }
