# Digital Human Engine Admin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build admin-managed digital human engine configurations and let users choose an enabled configuration when generating a digital human video.

**Architecture:** Add a Django model/admin for engine configs, expose a public safe config-list API, and route generation through a config resolver and adapter registry. Keep local FFmpeg as the working fallback while adding Jimeng/talking-avatar placeholders that fail clearly until provider credentials and docs are supplied.

**Tech Stack:** Django, Django REST Framework, Vue 3, Vite, FFmpeg, pytest.

---

## File Structure

- **Backend model/admin**
  - Modify: `backend/apps/trends/models.py`
  - Create: `backend/apps/trends/migrations/0014_digitalhumanengineconfig.py`
  - Modify: `backend/apps/trends/admin.py`
- **Backend engine services**
  - Modify: `backend/apps/trends/services/digital_human_video_service.py`
  - Create: `backend/apps/trends/services/digital_human_engines.py`
- **Backend API**
  - Modify: `backend/apps/trends/api/digital_human_views.py`
  - Modify: `backend/apps/trends/api/urls.py`
- **Backend tests**
  - Modify: `backend/tests/trends/test_digital_human_video.py`
- **Frontend**
  - Modify: `frontend/src/api/client.js`
  - Modify: `frontend/src/pages/DigitalHumanVideo.vue`

## Implementation Notes

- Do not expose `api_key` through any public API response.
- Do not silently fall back to local FFmpeg when a user explicitly selects a configured third-party placeholder.
- If no enabled config exists and no `config_id` is provided, use the implicit local FFmpeg fallback.
- Keep third-party Jimeng/talking-avatar adapters as explicit placeholders in this phase.
- Keep `backend/media/` runtime outputs ignored by git.
- Do not touch or delete `tools/logs/lt-2026-05-24.jsonl`.

### Task 1: Model And Admin Configs

**Files:**
- Modify: `backend/apps/trends/models.py`
- Create: `backend/apps/trends/migrations/0014_digitalhumanengineconfig.py`
- Modify: `backend/apps/trends/admin.py`
- Modify: `backend/tests/trends/test_digital_human_video.py`

- [ ] **Step 1: Write failing tests for config defaults and admin-safe behavior**

Append to `backend/tests/trends/test_digital_human_video.py`:

```python
from apps.trends.models import DigitalHumanEngineConfig


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
```

- [ ] **Step 2: Run tests and verify they fail**

Run from `D:\aiFire\backend`:

```powershell
$env:USE_SQLITE='1'; ..\.venv\Scripts\python.exe -m pytest tests/trends/test_digital_human_video.py::test_digital_human_engine_default_is_unique tests/trends/test_digital_human_video.py::test_digital_human_engine_str_returns_name -q
```

Expected: FAIL because `DigitalHumanEngineConfig` does not exist.

- [ ] **Step 3: Add model**

Append to `backend/apps/trends/models.py` after `DigitalHumanSessionLog`:

```python
class DigitalHumanEngineConfig(models.Model):
    class EngineType(models.TextChoices):
        LOCAL_FFMPEG = "local_ffmpeg", "Local FFmpeg"
        JIMENG_VISUAL = "jimeng_visual", "Jimeng visual"
        TALKING_AVATAR = "talking_avatar", "Talking avatar"

    class SubtitleMode(models.TextChoices):
        NONE = "none", "No subtitles"
        ZH = "zh", "Chinese subtitles"
        ZH_EN = "zh_en", "Chinese and English subtitles"

    name = models.CharField(max_length=128)
    engine_type = models.CharField(max_length=32, choices=EngineType.choices, default=EngineType.LOCAL_FFMPEG)
    is_enabled = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    api_base_url = models.URLField(blank=True, default="")
    api_key = models.CharField(max_length=255, blank=True, default="")
    model_name = models.CharField(max_length=128, blank=True, default="")
    avatar_id = models.CharField(max_length=128, blank=True, default="")
    voice_id = models.CharField(max_length=128, blank=True, default="")
    subtitle_mode = models.CharField(max_length=16, choices=SubtitleMode.choices, default=SubtitleMode.ZH_EN)
    default_prompt = models.TextField(blank=True, default="")
    extra_config = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_default", "name"]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_default:
            type(self).objects.exclude(pk=self.pk).filter(is_default=True).update(is_default=False)

    def __str__(self) -> str:
        return self.name
```

- [ ] **Step 4: Add migration**

Create `backend/apps/trends/migrations/0014_digitalhumanengineconfig.py`:

```python
# Generated manually for digital human engine configuration.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("trends", "0013_alter_generatedtitle_risk_level_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="DigitalHumanEngineConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=128)),
                (
                    "engine_type",
                    models.CharField(
                        choices=[
                            ("local_ffmpeg", "Local FFmpeg"),
                            ("jimeng_visual", "Jimeng visual"),
                            ("talking_avatar", "Talking avatar"),
                        ],
                        default="local_ffmpeg",
                        max_length=32,
                    ),
                ),
                ("is_enabled", models.BooleanField(default=True)),
                ("is_default", models.BooleanField(default=False)),
                ("api_base_url", models.URLField(blank=True, default="")),
                ("api_key", models.CharField(blank=True, default="", max_length=255)),
                ("model_name", models.CharField(blank=True, default="", max_length=128)),
                ("avatar_id", models.CharField(blank=True, default="", max_length=128)),
                ("voice_id", models.CharField(blank=True, default="", max_length=128)),
                (
                    "subtitle_mode",
                    models.CharField(
                        choices=[
                            ("none", "No subtitles"),
                            ("zh", "Chinese subtitles"),
                            ("zh_en", "Chinese and English subtitles"),
                        ],
                        default="zh_en",
                        max_length=16,
                    ),
                ),
                ("default_prompt", models.TextField(blank=True, default="")),
                ("extra_config", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["-is_default", "name"],
            },
        ),
    ]
```

- [ ] **Step 5: Register model in admin**

Modify the import list in `backend/apps/trends/admin.py` to include `DigitalHumanEngineConfig`, then add:

```python
@admin.register(DigitalHumanEngineConfig)
class DigitalHumanEngineConfigAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "engine_type",
        "is_enabled",
        "is_default",
        "subtitle_mode",
        "model_name",
        "updated_at",
    )
    search_fields = ("name", "engine_type", "model_name", "avatar_id", "voice_id")
    list_filter = ("engine_type", "is_enabled", "is_default", "subtitle_mode")
    fields = (
        "name",
        "engine_type",
        "is_enabled",
        "is_default",
        "api_base_url",
        "api_key",
        "model_name",
        "avatar_id",
        "voice_id",
        "subtitle_mode",
        "default_prompt",
        "extra_config",
    )
```

- [ ] **Step 6: Run model/admin tests**

Run:

```powershell
$env:USE_SQLITE='1'; ..\.venv\Scripts\python.exe -m pytest tests/trends/test_digital_human_video.py::test_digital_human_engine_default_is_unique tests/trends/test_digital_human_video.py::test_digital_human_engine_str_returns_name -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add backend/apps/trends/models.py backend/apps/trends/migrations/0014_digitalhumanengineconfig.py backend/apps/trends/admin.py backend/tests/trends/test_digital_human_video.py
git commit -m "feat: add digital human engine configs"
```

### Task 2: Config Resolution And Engine Metadata API

**Files:**
- Create: `backend/apps/trends/services/digital_human_engines.py`
- Modify: `backend/apps/trends/api/digital_human_views.py`
- Modify: `backend/apps/trends/api/urls.py`
- Modify: `backend/tests/trends/test_digital_human_video.py`

- [ ] **Step 1: Write failing tests for config list and resolution**

Append to `backend/tests/trends/test_digital_human_video.py`:

```python
from apps.trends.services.digital_human_engines import (
    engine_config_to_public_dict,
    resolve_engine_config,
)


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
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
$env:USE_SQLITE='1'; ..\.venv\Scripts\python.exe -m pytest tests/trends/test_digital_human_video.py::test_engine_config_list_hides_disabled_and_api_key tests/trends/test_digital_human_video.py::test_resolve_engine_config_rejects_disabled_config tests/trends/test_digital_human_video.py::test_engine_config_to_public_dict_has_labels -q
```

Expected: FAIL because service/API do not exist yet.

- [ ] **Step 3: Create engine config service**

Create `backend/apps/trends/services/digital_human_engines.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

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
    extra_config: dict | None = None


def enabled_engine_configs():
    return DigitalHumanEngineConfig.objects.filter(is_enabled=True).order_by("-is_default", "name")


def default_engine_config():
    config = enabled_engine_configs().filter(is_default=True).first()
    if config:
        return config
    config = enabled_engine_configs().first()
    if config:
        return config
    return ImplicitLocalEngineConfig(extra_config={})


def resolve_engine_config(config_id):
    if not config_id:
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
    default_config = next((item for item in configs if item["is_default"]), configs[0] if configs else None)
    return {
        "configs": configs,
        "default_config_id": default_config["id"] if default_config else None,
    }
```

- [ ] **Step 4: Add config list API view**

Modify `backend/apps/trends/api/digital_human_views.py` imports:

```python
from apps.trends.services.digital_human_engines import public_engine_config_payload
```

Add:

```python
class DigitalHumanVideoConfigListView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response(public_engine_config_payload(), status=status.HTTP_200_OK)
```

- [ ] **Step 5: Add config list route**

Modify `backend/apps/trends/api/urls.py` import list to include `DigitalHumanVideoConfigListView`, then add before the video create route:

```python
path("digital-human/video-configs/", DigitalHumanVideoConfigListView.as_view(), name="digital-human-video-config-list"),
```

- [ ] **Step 6: Run tests**

Run:

```powershell
$env:USE_SQLITE='1'; ..\.venv\Scripts\python.exe -m pytest tests/trends/test_digital_human_video.py::test_engine_config_list_hides_disabled_and_api_key tests/trends/test_digital_human_video.py::test_resolve_engine_config_rejects_disabled_config tests/trends/test_digital_human_video.py::test_engine_config_to_public_dict_has_labels -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add backend/apps/trends/services/digital_human_engines.py backend/apps/trends/api/digital_human_views.py backend/apps/trends/api/urls.py backend/tests/trends/test_digital_human_video.py
git commit -m "feat: expose digital human engine configs"
```

### Task 3: Adapter Registry And Selected Config Generation

**Files:**
- Modify: `backend/apps/trends/services/digital_human_video_service.py`
- Modify: `backend/apps/trends/services/digital_human_engines.py`
- Modify: `backend/apps/trends/api/digital_human_views.py`
- Modify: `backend/tests/trends/test_digital_human_video.py`

- [ ] **Step 1: Write failing adapter tests**

Append to `backend/tests/trends/test_digital_human_video.py`:

```python
@pytest.mark.django_db
def test_generation_with_jimeng_config_without_api_key_returns_clear_error():
    config = DigitalHumanEngineConfig.objects.create(
        name="Jimeng visual",
        engine_type=DigitalHumanEngineConfig.EngineType.JIMENG_VISUAL,
        is_enabled=True,
        is_default=True,
    )

    result = generate_digital_human_video(
        script="生成一条数字人视频",
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
def test_generation_response_includes_local_engine_config(monkeypatch):
    config = DigitalHumanEngineConfig.objects.create(
        name="Local selectable",
        engine_type=DigitalHumanEngineConfig.EngineType.LOCAL_FFMPEG,
        is_enabled=True,
        is_default=True,
    )

    monkeypatch.setattr("apps.trends.services.digital_human_video_service.find_ffmpeg_binary", lambda: None)
    result = generate_digital_human_video(
        script="生成一条数字人视频",
        audio_mode="default",
        video_mode="default",
        files={},
        config_id=str(config.id),
    )

    assert result["status"] == "failed"
    assert result["engine"] == "ffmpeg_composite"
    assert result["engine_config"]["id"] == config.id
    assert result["engine_config"]["name"] == "Local selectable"
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
$env:USE_SQLITE='1'; ..\.venv\Scripts\python.exe -m pytest tests/trends/test_digital_human_video.py::test_generation_with_jimeng_config_without_api_key_returns_clear_error tests/trends/test_digital_human_video.py::test_generation_response_includes_local_engine_config -q
```

Expected: FAIL because `generate_digital_human_video` has no `config_id` parameter and no adapters.

- [ ] **Step 3: Move existing FFmpeg body into helper**

In `backend/apps/trends/services/digital_human_video_service.py`, rename the existing `generate_digital_human_video` function body to:

```python
def generate_local_ffmpeg_video(*, script: str, audio_mode: str, video_mode: str, files, engine_config=None) -> dict:
    validate_generation_request(script=script, audio_mode=audio_mode, video_mode=video_mode, files=files)
    job_id = str(uuid.uuid4())
    paths = build_paths(job_id)
    ensure_dirs(paths)

    ffmpeg = find_ffmpeg_binary()
    if not ffmpeg:
        data = {"status": "failed", "message": "生成失败：未找到 ffmpeg，请安装或配置 FFMPEG_BINARY"}
        if engine_config is not None:
            data["engine"] = "ffmpeg_composite"
            data["engine_config"] = engine_config_to_result_dict(engine_config)
        return data

    try:
        ensure_default_assets(ffmpeg)
        audio_path = resolve_audio_path(audio_mode, files, paths)
        video_path = resolve_video_path(video_mode, files, paths)
        paths.subtitle_path.write_text(build_srt_content(script), encoding="utf-8")
        run_ffmpeg_composite(ffmpeg, video_path, audio_path, paths.subtitle_path, paths.output_path)
    except DigitalHumanVideoError:
        raise
    except subprocess.CalledProcessError as exc:
        message = (exc.stderr or exc.stdout or str(exc)).strip()
        data = {"status": "failed", "message": f"生成失败：{message[:240]}"}
        if engine_config is not None:
            data["engine"] = "ffmpeg_composite"
            data["engine_config"] = engine_config_to_result_dict(engine_config)
        return data

    return {
        "job_id": job_id,
        "status": "success",
        "engine": "ffmpeg_composite",
        "engine_config": engine_config_to_result_dict(engine_config) if engine_config is not None else None,
        "video_url": media_url_for_output(job_id),
        "download_url": f"/api/digital-human/videos/{job_id}/download/",
        "message": "生成完成",
    }
```

Add near the top of the same file:

```python
def engine_config_to_result_dict(config) -> dict:
    if config is None:
        return {}
    return {
        "id": getattr(config, "id", None),
        "name": getattr(config, "name", "Local digital human fallback"),
        "engine_type": getattr(config, "engine_type", "local_ffmpeg"),
        "subtitle_mode": getattr(config, "subtitle_mode", "zh_en"),
    }
```

- [ ] **Step 4: Implement adapters in `digital_human_engines.py`**

Append:

```python
class DigitalHumanEngineAdapter:
    engine_type = ""

    def generate(self, *, script: str, audio_mode: str, video_mode: str, files, config) -> dict:
        raise NotImplementedError


class LocalFfmpegEngineAdapter(DigitalHumanEngineAdapter):
    engine_type = DigitalHumanEngineConfig.EngineType.LOCAL_FFMPEG

    def generate(self, *, script: str, audio_mode: str, video_mode: str, files, config) -> dict:
        from apps.trends.services.digital_human_video_service import generate_local_ffmpeg_video

        return generate_local_ffmpeg_video(
            script=script,
            audio_mode=audio_mode,
            video_mode=video_mode,
            files=files,
            engine_config=config,
        )


class JimengVisualEngineAdapter(DigitalHumanEngineAdapter):
    engine_type = DigitalHumanEngineConfig.EngineType.JIMENG_VISUAL

    def generate(self, *, script: str, audio_mode: str, video_mode: str, files, config) -> dict:
        if not (config.api_key or "").strip():
            return {
                "status": "failed",
                "engine": self.engine_type,
                "engine_config": engine_config_to_public_dict(config),
                "message": "当前数字人配置缺少 API Key，请在后台配置。",
            }
        return {
            "status": "failed",
            "engine": self.engine_type,
            "engine_config": engine_config_to_public_dict(config),
            "message": "当前即梦数字人引擎尚未接入，请提供 API 文档后继续配置。",
        }


class TalkingAvatarEngineAdapter(DigitalHumanEngineAdapter):
    engine_type = DigitalHumanEngineConfig.EngineType.TALKING_AVATAR

    def generate(self, *, script: str, audio_mode: str, video_mode: str, files, config) -> dict:
        if not (config.api_key or "").strip():
            return {
                "status": "failed",
                "engine": self.engine_type,
                "engine_config": engine_config_to_public_dict(config),
                "message": "当前口型数字人配置缺少 API Key，请在后台配置。",
            }
        return {
            "status": "failed",
            "engine": self.engine_type,
            "engine_config": engine_config_to_public_dict(config),
            "message": "当前口型数字人引擎尚未接入，请提供 API 文档后继续配置。",
        }


ADAPTERS = {
    LocalFfmpegEngineAdapter.engine_type: LocalFfmpegEngineAdapter(),
    JimengVisualEngineAdapter.engine_type: JimengVisualEngineAdapter(),
    TalkingAvatarEngineAdapter.engine_type: TalkingAvatarEngineAdapter(),
}


def get_engine_adapter(engine_type: str) -> DigitalHumanEngineAdapter:
    adapter = ADAPTERS.get(engine_type)
    if not adapter:
        raise DigitalHumanVideoError("当前数字人引擎尚未接入", 500)
    return adapter
```

- [ ] **Step 5: Recreate public `generate_digital_human_video` wrapper**

In `backend/apps/trends/services/digital_human_video_service.py`, add imports inside the function to avoid circular imports:

```python
def generate_digital_human_video(*, script: str, audio_mode: str, video_mode: str, files, config_id=None) -> dict:
    validate_generation_request(script=script, audio_mode=audio_mode, video_mode=video_mode, files=files)
    from apps.trends.services.digital_human_engines import get_engine_adapter, resolve_engine_config

    config = resolve_engine_config(config_id)
    adapter = get_engine_adapter(config.engine_type)
    return adapter.generate(script=script, audio_mode=audio_mode, video_mode=video_mode, files=files, config=config)
```

- [ ] **Step 6: Pass `config_id` from API view**

Modify `DigitalHumanVideoCreateView.post`:

```python
data = generate_digital_human_video(
    script=request.data.get("script") or "",
    audio_mode=request.data.get("audio_mode") or "default",
    video_mode=request.data.get("video_mode") or "default",
    files=request.FILES,
    config_id=request.data.get("config_id"),
)
```

- [ ] **Step 7: Run adapter tests**

Run:

```powershell
$env:USE_SQLITE='1'; ..\.venv\Scripts\python.exe -m pytest tests/trends/test_digital_human_video.py::test_generation_with_jimeng_config_without_api_key_returns_clear_error tests/trends/test_digital_human_video.py::test_generation_response_includes_local_engine_config -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```powershell
git add backend/apps/trends/services/digital_human_video_service.py backend/apps/trends/services/digital_human_engines.py backend/apps/trends/api/digital_human_views.py backend/tests/trends/test_digital_human_video.py
git commit -m "feat: route digital human video through engine configs"
```

### Task 4: Bilingual Subtitle Structure

**Files:**
- Modify: `backend/apps/trends/services/digital_human_video_service.py`
- Modify: `backend/tests/trends/test_digital_human_video.py`

- [ ] **Step 1: Write failing bilingual subtitle test**

Append:

```python
from apps.trends.services.digital_human_video_service import build_bilingual_srt_content


def test_build_bilingual_srt_content_contains_chinese_and_english_lines():
    content = build_bilingual_srt_content("你好世界", "Hello world")

    assert "你好世界" in content
    assert "Hello world" in content
    assert "00:00:00,000 --> 00:00:08,000" in content
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```powershell
$env:USE_SQLITE='1'; ..\.venv\Scripts\python.exe -m pytest tests/trends/test_digital_human_video.py::test_build_bilingual_srt_content_contains_chinese_and_english_lines -q
```

Expected: FAIL because `build_bilingual_srt_content` does not exist.

- [ ] **Step 3: Add bilingual subtitle helper**

Add to `backend/apps/trends/services/digital_human_video_service.py` after `build_srt_content`:

```python
def build_bilingual_srt_content(script_zh: str, script_en: str) -> str:
    clean_zh = " ".join((script_zh or "").split())
    clean_en = " ".join((script_en or "").split())
    lines = [line for line in [clean_zh, clean_en] if line]
    return f"1\n00:00:00,000 --> 00:00:08,000\n{' / '.join(lines)}\n"
```

- [ ] **Step 4: Use subtitle mode in local generation**

In `generate_local_ffmpeg_video`, replace:

```python
paths.subtitle_path.write_text(build_srt_content(script), encoding="utf-8")
```

with:

```python
subtitle_mode = getattr(engine_config, "subtitle_mode", "zh_en")
if subtitle_mode == "none":
    paths.subtitle_path.write_text("", encoding="utf-8")
elif subtitle_mode == "zh_en":
    paths.subtitle_path.write_text(build_bilingual_srt_content(script, script), encoding="utf-8")
else:
    paths.subtitle_path.write_text(build_srt_content(script), encoding="utf-8")
```

Note: this phase uses source text as the English line only as a non-provider placeholder. Real translation is a later provider-specific integration.

- [ ] **Step 5: Run subtitle test**

Run:

```powershell
$env:USE_SQLITE='1'; ..\.venv\Scripts\python.exe -m pytest tests/trends/test_digital_human_video.py::test_build_bilingual_srt_content_contains_chinese_and_english_lines -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add backend/apps/trends/services/digital_human_video_service.py backend/tests/trends/test_digital_human_video.py
git commit -m "feat: add bilingual subtitle structure"
```

### Task 5: Frontend Config Picker

**Files:**
- Modify: `frontend/src/api/client.js`
- Modify: `frontend/src/pages/DigitalHumanVideo.vue`

- [ ] **Step 1: Add frontend API helper**

Modify `frontend/src/api/client.js` by adding:

```javascript
export async function fetchDigitalHumanVideoConfigs() {
  const response = await fetch("/api/digital-human/video-configs/", {
    credentials: "same-origin",
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.message || payload.detail || "数字人配置加载失败");
  }
  return payload;
}
```

Update `generateDigitalHumanVideo` signature to include `configId = null`, then add:

```javascript
if (configId) formData.set("config_id", String(configId));
```

- [ ] **Step 2: Update Vue script**

Modify `frontend/src/pages/DigitalHumanVideo.vue` imports:

```javascript
import { computed, onMounted, ref } from "vue";
import { fetchDigitalHumanVideoConfigs, generateDigitalHumanVideo } from "../api/client";
```

Add refs:

```javascript
const configs = ref([]);
const selectedConfigId = ref("");
const configError = ref("");
```

Add:

```javascript
const selectedConfig = computed(() => configs.value.find((item) => String(item.id) === String(selectedConfigId.value)) || null);

async function loadConfigs() {
  try {
    const payload = await fetchDigitalHumanVideoConfigs();
    configs.value = payload.configs || [];
    selectedConfigId.value = payload.default_config_id ? String(payload.default_config_id) : (configs.value[0]?.id ? String(configs.value[0].id) : "");
  } catch (err) {
    configError.value = err.message || "数字人配置加载失败";
  }
}

onMounted(loadConfigs);
```

In `submitVideo`, pass:

```javascript
configId: selectedConfigId.value || null,
```

- [ ] **Step 3: Add config picker markup**

Inside the form before the script textarea:

```vue
<section class="config-panel">
  <label class="script-field">
    数字人配置
    <select v-model="selectedConfigId">
      <option v-if="!configs.length" value="">本地默认配置</option>
      <option v-for="config in configs" :key="config.id" :value="String(config.id)">
        {{ config.name }} · {{ config.engine_label }} · {{ config.subtitle_label }}
      </option>
    </select>
  </label>
  <p v-if="selectedConfig" class="config-summary">
    当前配置：{{ selectedConfig.name }} / {{ selectedConfig.engine_label }} / {{ selectedConfig.subtitle_label }}
  </p>
  <p v-if="configError" class="video-error">{{ configError }}</p>
</section>
```

- [ ] **Step 4: Add CSS**

In the same `<style scoped>` block:

```css
.config-panel {
  border: 1px solid #d8c9b1;
  border-radius: 8px;
  display: grid;
  gap: 8px;
  margin-bottom: 14px;
  padding: 13px;
}

.config-summary {
  color: var(--ink-soft);
  font-size: 13px;
  margin: 0;
}
```

- [ ] **Step 5: Run frontend build**

Run from `D:\aiFire\frontend`:

```powershell
& 'D:\Program Files\nodejs\npm.cmd' run build
```

Expected: build succeeds.

- [ ] **Step 6: Commit**

```powershell
git add frontend/src/api/client.js frontend/src/pages/DigitalHumanVideo.vue
git commit -m "feat: let users choose digital human config"
```

### Task 6: Integration Verification

**Files:**
- Modify only if verification reveals a bug.

- [ ] **Step 1: Run backend tests**

Run from `D:\aiFire\backend`:

```powershell
$env:USE_SQLITE='1'; ..\.venv\Scripts\python.exe -m pytest tests/trends/test_digital_human_video.py tests/trends/test_digital_human_chat.py tests/trends/test_ensure_daily_fetch.py -q
```

Expected: PASS.

- [ ] **Step 2: Run Django check**

Run:

```powershell
$env:USE_SQLITE='1'; ..\.venv\Scripts\python.exe manage.py check
```

Expected: `System check identified no issues`.

- [ ] **Step 3: Run frontend build**

Run from `D:\aiFire\frontend`:

```powershell
& 'D:\Program Files\nodejs\npm.cmd' run build
```

Expected: build succeeds.

- [ ] **Step 4: Apply migrations locally**

Run from `D:\aiFire\backend`:

```powershell
$env:USE_SQLITE='1'; ..\.venv\Scripts\python.exe manage.py migrate
```

Expected: migration `0014_digitalhumanengineconfig` applies successfully or is already applied.

- [ ] **Step 5: Browser verification**

Open:

```text
http://127.0.0.1:5173/digital-human-video
```

Verify:

- The page shows a digital human config selector.
- With no enabled configs, local fallback still generates mp4.
- After creating a local config in Django Admin, the page lists it.
- Selecting local config generates mp4.
- Selecting a Jimeng placeholder config without API key shows a clear configuration error.

- [ ] **Step 6: Final commit if fixes were needed**

If any verification fix was required:

```powershell
git add <changed-files>
git commit -m "fix: verify digital human engine config flow"
```

## Self-Review

1. **Spec coverage:** The plan covers admin-managed configs, user-facing config selection, safe config list API, local fallback, placeholder third-party adapters, bilingual subtitle structure, frontend display, and verification. Real third-party API calls remain out of scope until credentials/docs are supplied.
2. **Placeholder scan:** Third-party adapters intentionally return explicit not-connected errors. No implementation step uses vague placeholder instructions.
3. **Type consistency:** Model fields are `is_enabled`, `is_default`, `engine_type`, `subtitle_mode`; public request uses `config_id`; response metadata uses `engine_config`. These names are consistent across backend, API, and frontend tasks.
