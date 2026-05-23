# Digital Human Video Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an independent digital human video page where users can use default or uploaded audio/video, generate a real downloadable mp4, and navigate to it from the app menu.

**Architecture:** Add a focused Django service that validates inputs, prepares default/uploaded media, invokes FFmpeg, and exposes create/download API endpoints. Add a Vue route and page for the generation workflow, plus a simple app shell menu in `App.vue`.

**Tech Stack:** Django, Django REST Framework, Vue 3, Vite, FFmpeg subprocess integration, pytest, npm build.

---

## File Structure

- **Backend settings and URLs**
  - Modify: `backend/config/settings.py`
  - Modify: `backend/config/urls.py`
  - Modify: `backend/apps/trends/api/urls.py`
- **Backend service and API**
  - Create: `backend/apps/trends/services/digital_human_video_service.py`
  - Modify: `backend/apps/trends/api/digital_human_views.py`
  - Create: `backend/tests/trends/test_digital_human_video.py`
- **Frontend API and routing**
  - Modify: `frontend/src/api/client.js`
  - Modify: `frontend/src/router.js`
  - Modify: `frontend/src/App.vue`
  - Modify: `frontend/src/assets/main.css`
  - Create: `frontend/src/pages/DigitalHumanVideo.vue`
- **Docs**
  - Modify: `README.md`

## Implementation Notes

- Do not create database models for first version. The generated `job_id` is a UUID and the output file path is derived from that UUID.
- Generated runtime files live under `backend/media/digital_human/`, already ignored by git through `backend/media/`.
- The service must return a clear failure response if FFmpeg is not available. It must not pretend a video was generated.
- Tests should mock subprocess work for API contracts and file download behavior; full FFmpeg integration is verified manually when FFmpeg is available.
- Use native PowerShell commands in this repo. Do not use recursive delete commands. If a test creates files, use pytest `tmp_path` or Django `override_settings(MEDIA_ROOT=tmp_path)`.

### Task 1: Backend Media Settings

**Files:**
- Modify: `backend/config/settings.py`
- Modify: `backend/config/urls.py`

- [ ] **Step 1: Write a failing settings test**

Add these tests to `backend/tests/trends/test_digital_human_video.py`:

```python
from django.conf import settings


def test_media_settings_are_configured():
    assert settings.MEDIA_URL == "/media/"
    assert settings.MEDIA_ROOT.name == "media"
```

- [ ] **Step 2: Run the failing test**

Run from `D:\aiFire\backend`:

```powershell
$env:USE_SQLITE='1'; ..\.venv\Scripts\python.exe -m pytest tests/trends/test_digital_human_video.py::test_media_settings_are_configured -q
```

Expected: FAIL because `MEDIA_URL` or `MEDIA_ROOT` is missing.

- [ ] **Step 3: Configure media settings**

Append this near the existing static settings in `backend/config/settings.py`:

```python
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
```

- [ ] **Step 4: Expose media in development**

Update `backend/config/urls.py` imports and append static media serving:

```python
from django.conf import settings
from django.conf.urls.static import static
```

At the bottom of the file:

```python
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

- [ ] **Step 5: Run the settings test**

Run:

```powershell
$env:USE_SQLITE='1'; ..\.venv\Scripts\python.exe -m pytest tests/trends/test_digital_human_video.py::test_media_settings_are_configured -q
```

Expected: PASS.

- [ ] **Step 6: Commit media configuration**

```powershell
git add backend/config/settings.py backend/config/urls.py backend/tests/trends/test_digital_human_video.py
git commit -m "feat: configure media storage for digital human videos"
```

### Task 2: Video Generation Service Contracts

**Files:**
- Create: `backend/apps/trends/services/digital_human_video_service.py`
- Modify: `backend/tests/trends/test_digital_human_video.py`

- [ ] **Step 1: Write service validation tests**

Add this to `backend/tests/trends/test_digital_human_video.py`:

```python
import pytest

from apps.trends.services.digital_human_video_service import (
    DigitalHumanVideoError,
    validate_generation_request,
)


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
```

- [ ] **Step 2: Run the failing service tests**

Run:

```powershell
$env:USE_SQLITE='1'; ..\.venv\Scripts\python.exe -m pytest tests/trends/test_digital_human_video.py::test_validate_generation_request_rejects_short_script tests/trends/test_digital_human_video.py::test_validate_generation_request_requires_upload_audio_file tests/trends/test_digital_human_video.py::test_validate_generation_request_requires_upload_video_file -q
```

Expected: FAIL because the service module does not exist.

- [ ] **Step 3: Create the service error and validation functions**

Create `backend/apps/trends/services/digital_human_video_service.py`:

```python
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
```

- [ ] **Step 4: Run service validation tests**

Run:

```powershell
$env:USE_SQLITE='1'; ..\.venv\Scripts\python.exe -m pytest tests/trends/test_digital_human_video.py::test_validate_generation_request_rejects_short_script tests/trends/test_digital_human_video.py::test_validate_generation_request_requires_upload_audio_file tests/trends/test_digital_human_video.py::test_validate_generation_request_requires_upload_video_file -q
```

Expected: PASS.

- [ ] **Step 5: Commit service validation**

```powershell
git add backend/apps/trends/services/digital_human_video_service.py backend/tests/trends/test_digital_human_video.py
git commit -m "feat: add digital human video request validation"
```

### Task 3: Service File Handling and FFmpeg Command

**Files:**
- Modify: `backend/apps/trends/services/digital_human_video_service.py`
- Modify: `backend/tests/trends/test_digital_human_video.py`

- [ ] **Step 1: Write tests for subtitles and command failure**

Add this to `backend/tests/trends/test_digital_human_video.py`:

```python
from django.test import override_settings

from apps.trends.services.digital_human_video_service import (
    build_srt_content,
    generate_digital_human_video,
)


def test_build_srt_content_escapes_blank_script():
    content = build_srt_content("第一句\n\n第二句")
    assert "1" in content
    assert "00:00:00,000 --> 00:00:08,000" in content
    assert "第一句 第二句" in content


@override_settings(MEDIA_URL="/media/")
def test_generate_digital_human_video_returns_failed_when_ffmpeg_missing(tmp_path, monkeypatch):
    monkeypatch.setattr("apps.trends.services.digital_human_video_service.digital_human_media_root", lambda: tmp_path / "digital_human")
    monkeypatch.setattr("apps.trends.services.digital_human_video_service.find_ffmpeg_binary", lambda: None)

    result = generate_digital_human_video(
        script="生成一条默认视频",
        audio_mode="default",
        video_mode="default",
        files={},
    )

    assert result["status"] == "failed"
    assert "ffmpeg" in result["message"].lower()
```

- [ ] **Step 2: Run failing tests**

Run:

```powershell
$env:USE_SQLITE='1'; ..\.venv\Scripts\python.exe -m pytest tests/trends/test_digital_human_video.py::test_build_srt_content_escapes_blank_script tests/trends/test_digital_human_video.py::test_generate_digital_human_video_returns_failed_when_ffmpeg_missing -q
```

Expected: FAIL because functions are missing.

- [ ] **Step 3: Implement subtitle, default asset, upload, and FFmpeg helpers**

Append to `backend/apps/trends/services/digital_human_video_service.py`:

```python
import os
import shutil
import subprocess
import uuid

from django.core.files.uploadedfile import UploadedFile


def build_srt_content(script: str) -> str:
    clean_script = " ".join((script or "").split())
    return f"1\n00:00:00,000 --> 00:00:08,000\n{clean_script}\n"


def find_ffmpeg_binary() -> str | None:
    configured = os.getenv("FFMPEG_BINARY", "").strip()
    if configured and Path(configured).exists():
        return configured
    return shutil.which("ffmpeg")


def ensure_dirs(paths: GenerationPaths) -> None:
    paths.output_path.parent.mkdir(parents=True, exist_ok=True)
    paths.subtitle_path.parent.mkdir(parents=True, exist_ok=True)
    paths.upload_dir.mkdir(parents=True, exist_ok=True)


def build_paths(job_id: str) -> GenerationPaths:
    root = digital_human_media_root()
    return GenerationPaths(
        job_id=job_id,
        output_path=root / "outputs" / f"{job_id}.mp4",
        subtitle_path=root / "outputs" / f"{job_id}.srt",
        upload_dir=root / "uploads" / job_id,
    )


def validate_upload(file: UploadedFile, allowed_extensions: set[str], label: str) -> None:
    suffix = Path(file.name or "").suffix.lower()
    if suffix not in allowed_extensions:
        raise DigitalHumanVideoError(f"{label}文件类型不支持", 400)
    if file.size and file.size > MAX_UPLOAD_BYTES:
        raise DigitalHumanVideoError(f"{label}文件不能超过 100MB", 400)


def save_upload(file: UploadedFile, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as dest:
        for chunk in file.chunks():
            dest.write(chunk)
    return target


def default_audio_path() -> Path:
    return digital_human_media_root() / "defaults" / "default_audio.wav"


def default_video_path() -> Path:
    return digital_human_media_root() / "defaults" / "default_video.mp4"


def resolve_audio_path(audio_mode: str, files, paths: GenerationPaths) -> Path:
    if audio_mode == "default":
        return default_audio_path()
    audio_file = files["audio_file"]
    validate_upload(audio_file, AUDIO_EXTENSIONS, "音频")
    return save_upload(audio_file, paths.upload_dir / f"input_audio{Path(audio_file.name).suffix.lower()}")


def resolve_video_path(video_mode: str, files, paths: GenerationPaths) -> Path:
    if video_mode == "default":
        return default_video_path()
    video_file = files["video_file"]
    validate_upload(video_file, VIDEO_EXTENSIONS, "视频")
    return save_upload(video_file, paths.upload_dir / f"input_video{Path(video_file.name).suffix.lower()}")


def ensure_default_assets(ffmpeg: str) -> None:
    audio = default_audio_path()
    video = default_video_path()
    audio.parent.mkdir(parents=True, exist_ok=True)
    video.parent.mkdir(parents=True, exist_ok=True)
    if not audio.exists():
        subprocess.run(
            [ffmpeg, "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", "8", str(audio)],
            check=True,
            capture_output=True,
            text=True,
        )
    if not video.exists():
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-f",
                "lavfi",
                "-i",
                "color=c=0x113a35:s=720x1280:r=25",
                "-t",
                "8",
                "-vf",
                "drawtext=text='AI Digital Human':fontcolor=white:fontsize=52:x=(w-text_w)/2:y=(h-text_h)/2",
                str(video),
            ],
            check=True,
            capture_output=True,
            text=True,
        )


def media_url_for_output(job_id: str) -> str:
    return f"{settings.MEDIA_URL.rstrip('/')}/digital_human/outputs/{job_id}.mp4"


def run_ffmpeg_composite(ffmpeg: str, video_path: Path, audio_path: Path, subtitle_path: Path, output_path: Path) -> None:
    subtitle_arg = str(subtitle_path).replace("\\", "/").replace(":", "\\:")
    cmd = [
        ffmpeg,
        "-y",
        "-stream_loop",
        "-1",
        "-i",
        str(video_path),
        "-i",
        str(audio_path),
        "-vf",
        f"subtitles='{subtitle_arg}'",
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-shortest",
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        "-pix_fmt",
        "yuv420p",
        str(output_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def generate_digital_human_video(*, script: str, audio_mode: str, video_mode: str, files) -> dict:
    validate_generation_request(script=script, audio_mode=audio_mode, video_mode=video_mode, files=files)
    job_id = str(uuid.uuid4())
    paths = build_paths(job_id)
    ensure_dirs(paths)

    ffmpeg = find_ffmpeg_binary()
    if not ffmpeg:
        return {"status": "failed", "message": "生成失败：未找到 ffmpeg，请安装或配置 FFMPEG_BINARY"}

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
        return {"status": "failed", "message": f"生成失败：{message[:240]}"}

    return {
        "job_id": job_id,
        "status": "success",
        "engine": "ffmpeg_composite",
        "video_url": media_url_for_output(job_id),
        "download_url": f"/api/digital-human/videos/{job_id}/download/",
        "message": "生成完成",
    }
```

- [ ] **Step 4: Run service tests**

Run:

```powershell
$env:USE_SQLITE='1'; ..\.venv\Scripts\python.exe -m pytest tests/trends/test_digital_human_video.py -q
```

Expected: PASS for the service tests written so far.

- [ ] **Step 5: Commit generation service**

```powershell
git add backend/apps/trends/services/digital_human_video_service.py backend/tests/trends/test_digital_human_video.py
git commit -m "feat: add ffmpeg digital human video service"
```

### Task 4: Video Create and Download API

**Files:**
- Modify: `backend/apps/trends/api/digital_human_views.py`
- Modify: `backend/apps/trends/api/urls.py`
- Modify: `backend/tests/trends/test_digital_human_video.py`

- [ ] **Step 1: Write API tests**

Add this to `backend/tests/trends/test_digital_human_video.py`:

```python
from pathlib import Path

from django.test import override_settings
from rest_framework.test import APIClient


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
@override_settings(MEDIA_ROOT=None)
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
```

- [ ] **Step 2: Run failing API tests**

Run:

```powershell
$env:USE_SQLITE='1'; ..\.venv\Scripts\python.exe -m pytest tests/trends/test_digital_human_video.py::test_digital_human_video_create_rejects_short_script tests/trends/test_digital_human_video.py::test_digital_human_video_create_success tests/trends/test_digital_human_video.py::test_digital_human_video_download_returns_file -q
```

Expected: FAIL because API classes/routes are missing.

- [ ] **Step 3: Add API views**

Append to `backend/apps/trends/api/digital_human_views.py`:

```python
from pathlib import Path

from django.conf import settings
from django.http import FileResponse

from apps.trends.services.digital_human_video_service import (
    DigitalHumanVideoError,
    generate_digital_human_video,
)


class DigitalHumanVideoCreateView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        try:
            data = generate_digital_human_video(
                script=request.data.get("script") or "",
                audio_mode=request.data.get("audio_mode") or "default",
                video_mode=request.data.get("video_mode") or "default",
                files=request.FILES,
            )
        except DigitalHumanVideoError as exc:
            return Response({"status": "failed", "message": exc.message}, status=exc.status_code)
        http_status = status.HTTP_200_OK if data.get("status") == "success" else status.HTTP_500_INTERNAL_SERVER_ERROR
        return Response(data, status=http_status)


class DigitalHumanVideoDownloadView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, job_id: str):
        safe_job_id = Path(job_id).name
        output_path = Path(settings.MEDIA_ROOT) / "digital_human" / "outputs" / f"{safe_job_id}.mp4"
        if not output_path.exists():
            return Response({"detail": "视频不存在或已过期"}, status=status.HTTP_404_NOT_FOUND)
        return FileResponse(output_path.open("rb"), as_attachment=True, filename=f"digital-human-{safe_job_id}.mp4", content_type="video/mp4")
```

- [ ] **Step 4: Add API routes**

Update `backend/apps/trends/api/urls.py` import:

```python
from apps.trends.api.digital_human_views import (
    DigitalHumanChatView,
    DigitalHumanVideoCreateView,
    DigitalHumanVideoDownloadView,
)
```

Add routes:

```python
path("digital-human/videos/", DigitalHumanVideoCreateView.as_view(), name="digital-human-video-create"),
path("digital-human/videos/<str:job_id>/download/", DigitalHumanVideoDownloadView.as_view(), name="digital-human-video-download"),
```

- [ ] **Step 5: Run API tests**

Run:

```powershell
$env:USE_SQLITE='1'; ..\.venv\Scripts\python.exe -m pytest tests/trends/test_digital_human_video.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit video API**

```powershell
git add backend/apps/trends/api/digital_human_views.py backend/apps/trends/api/urls.py backend/tests/trends/test_digital_human_video.py
git commit -m "feat: expose digital human video generation API"
```

### Task 5: Frontend API and App Menu

**Files:**
- Modify: `frontend/src/api/client.js`
- Modify: `frontend/src/router.js`
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/assets/main.css`

- [ ] **Step 1: Add frontend API helper**

Append to `frontend/src/api/client.js`:

```javascript
export async function generateDigitalHumanVideo({ script, audioMode = "default", videoMode = "default", audioFile = null, videoFile = null }) {
  const formData = new FormData();
  formData.set("script", script);
  formData.set("audio_mode", audioMode);
  formData.set("video_mode", videoMode);
  if (audioFile) formData.set("audio_file", audioFile);
  if (videoFile) formData.set("video_file", videoFile);

  const csrfToken = readCookie("csrftoken");
  const response = await fetch("/api/digital-human/videos/", {
    method: "POST",
    credentials: "same-origin",
    headers: { "X-CSRFToken": csrfToken },
    body: formData,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.message || payload.detail || "数字人视频生成失败");
  }
  return payload;
}
```

- [ ] **Step 2: Add route placeholder**

Modify `frontend/src/router.js`:

```javascript
import DigitalHumanVideo from "./pages/DigitalHumanVideo.vue";
```

Add route:

```javascript
{ path: "/digital-human-video", component: DigitalHumanVideo },
```

- [ ] **Step 3: Add global app shell menu**

Replace `frontend/src/App.vue` with:

```vue
<template>
  <div class="app-shell">
    <header class="app-header">
      <RouterLink to="/" class="app-brand">AI Trend Studio</RouterLink>
      <nav class="app-nav" aria-label="主导航">
        <RouterLink to="/">热词洞察</RouterLink>
        <RouterLink to="/digital-human-video">数字人视频</RouterLink>
      </nav>
    </header>
    <RouterView />
  </div>
</template>
```

- [ ] **Step 4: Add app shell CSS**

Append to `frontend/src/assets/main.css`:

```css
.app-shell {
  min-height: 100vh;
}

.app-header {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 14px min(4vw, 34px);
  border-bottom: 1px solid rgba(215, 203, 181, 0.8);
  background: rgba(255, 253, 250, 0.9);
  backdrop-filter: blur(14px);
}

.app-brand {
  font-weight: 900;
  color: var(--ink-strong);
}

.app-nav {
  display: flex;
  align-items: center;
  gap: 8px;
}

.app-nav a {
  border: 1px solid transparent;
  border-radius: 999px;
  color: var(--ink-soft);
  font-size: 14px;
  font-weight: 800;
  padding: 8px 12px;
}

.app-nav a.router-link-active {
  border-color: #7bcfc4;
  background: #e8fffb;
  color: var(--brand-strong);
}

@media (max-width: 640px) {
  .app-header {
    align-items: flex-start;
    flex-direction: column;
  }
}
```

- [ ] **Step 5: Create temporary page file to satisfy route import**

Create `frontend/src/pages/DigitalHumanVideo.vue`:

```vue
<template>
  <main class="digital-video-page">
    <section class="digital-video-hero">
      <p class="section-kicker">Digital Human Video</p>
      <h1>数字人视频生成</h1>
      <p>输入脚本，选择默认或上传素材，生成可下载 mp4。</p>
    </section>
  </main>
</template>
```

- [ ] **Step 6: Run frontend build**

Run from `D:\aiFire\frontend`:

```powershell
& 'D:\Program Files\nodejs\npm.cmd' run build
```

Expected: build succeeds.

- [ ] **Step 7: Commit menu and API helper**

```powershell
git add frontend/src/api/client.js frontend/src/router.js frontend/src/App.vue frontend/src/assets/main.css frontend/src/pages/DigitalHumanVideo.vue
git commit -m "feat: add digital human video navigation"
```

### Task 6: Frontend Digital Human Video Page

**Files:**
- Modify: `frontend/src/pages/DigitalHumanVideo.vue`

- [ ] **Step 1: Replace temporary page with full component**

Replace `frontend/src/pages/DigitalHumanVideo.vue`:

```vue
<script setup>
import { computed, ref } from "vue";
import { generateDigitalHumanVideo } from "../api/client";

const scriptText = ref("");
const audioMode = ref("default");
const videoMode = ref("default");
const audioFile = ref(null);
const videoFile = ref(null);
const loading = ref(false);
const error = ref("");
const result = ref(null);

const canSubmit = computed(() => scriptText.value.trim().length >= 2 && !loading.value);

function onAudioFile(event) {
  audioFile.value = event.target.files?.[0] || null;
}

function onVideoFile(event) {
  videoFile.value = event.target.files?.[0] || null;
}

async function submitVideo() {
  if (scriptText.value.trim().length < 2) {
    error.value = "请输入至少 2 个字的口播脚本";
    return;
  }
  loading.value = true;
  error.value = "";
  result.value = null;
  try {
    result.value = await generateDigitalHumanVideo({
      script: scriptText.value.trim(),
      audioMode: audioMode.value,
      videoMode: videoMode.value,
      audioFile: audioMode.value === "upload" ? audioFile.value : null,
      videoFile: videoMode.value === "upload" ? videoFile.value : null,
    });
  } catch (err) {
    error.value = err.message || "数字人视频生成失败";
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <main class="digital-video-page">
    <section class="digital-video-hero">
      <p class="section-kicker">Digital Human Video</p>
      <h1>数字人视频生成</h1>
      <p>输入脚本，选择默认或上传素材，生成可下载 mp4。</p>
    </section>

    <section class="digital-video-layout">
      <form class="generator-panel" @submit.prevent="submitVideo">
        <label class="script-field">
          口播脚本
          <textarea v-model="scriptText" rows="7" placeholder="请输入想让数字人播报的内容"></textarea>
        </label>

        <div class="source-grid">
          <fieldset>
            <legend>音频来源</legend>
            <label><input v-model="audioMode" type="radio" value="default" /> 默认音频</label>
            <label><input v-model="audioMode" type="radio" value="upload" /> 上传音频</label>
            <input v-if="audioMode === 'upload'" type="file" accept=".mp3,.wav,.m4a,.aac,audio/*" @change="onAudioFile" />
          </fieldset>

          <fieldset>
            <legend>视频来源</legend>
            <label><input v-model="videoMode" type="radio" value="default" /> 默认视频</label>
            <label><input v-model="videoMode" type="radio" value="upload" /> 上传视频</label>
            <input v-if="videoMode === 'upload'" type="file" accept=".mp4,.mov,.webm,video/*" @change="onVideoFile" />
          </fieldset>
        </div>

        <p v-if="error" class="video-error">{{ error }}</p>
        <button class="generate-button" type="submit" :disabled="!canSubmit">
          {{ loading ? "生成中..." : "生成视频" }}
        </button>
      </form>

      <aside class="result-panel">
        <div class="result-head">
          <p class="section-kicker">Result</p>
          <h2>生成结果</h2>
        </div>
        <p v-if="loading" class="result-status">正在合成视频，请稍候。</p>
        <p v-else-if="!result" class="result-status">等待生成任务。</p>
        <template v-else>
          <p class="result-status">{{ result.message }}</p>
          <video v-if="result.video_url" :src="result.video_url" controls></video>
          <a v-if="result.download_url" class="download-button" :href="result.download_url">下载 mp4</a>
        </template>
      </aside>
    </section>
  </main>
</template>

<style scoped>
.digital-video-page {
  width: min(1120px, 94vw);
  margin: 28px auto 48px;
  display: grid;
  gap: 18px;
}

.digital-video-hero {
  border: 1px solid var(--line);
  border-radius: 8px;
  background: linear-gradient(135deg, #fffdf8 0%, #e8fffb 100%);
  padding: 24px;
}

.digital-video-hero h1 {
  margin: 8px 0;
  font-size: clamp(28px, 4vw, 42px);
}

.digital-video-hero p {
  color: var(--ink-soft);
  margin: 0;
}

.digital-video-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(320px, 0.9fr);
  gap: 16px;
  align-items: start;
}

.generator-panel,
.result-panel {
  border: 1px solid var(--line);
  border-radius: 8px;
  background: rgba(255, 253, 250, 0.92);
  box-shadow: var(--shadow-soft);
  padding: 18px;
}

.script-field {
  display: grid;
  gap: 8px;
  color: var(--ink-soft);
  font-size: 14px;
  font-weight: 800;
}

.script-field textarea {
  min-height: 170px;
}

.source-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 14px;
}

fieldset {
  border: 1px solid #d8c9b1;
  border-radius: 8px;
  display: grid;
  gap: 9px;
  margin: 0;
  padding: 13px;
}

legend {
  color: var(--brand-strong);
  font-weight: 900;
  padding: 0 5px;
}

fieldset label {
  align-items: center;
  display: flex;
  gap: 8px;
  color: var(--ink-strong);
}

input[type="radio"] {
  width: auto;
}

.generate-button,
.download-button {
  border: 1px solid #7bcfc4;
  border-radius: 8px;
  background: #e8fffb;
  color: var(--brand-strong);
  cursor: pointer;
  display: inline-flex;
  font-weight: 900;
  margin-top: 14px;
  padding: 10px 14px;
}

.generate-button:disabled {
  cursor: wait;
  opacity: 0.58;
}

.video-error {
  color: var(--danger);
  margin: 12px 0 0;
}

.result-head h2 {
  margin: 4px 0 12px;
}

.result-status {
  color: var(--ink-soft);
  margin: 0 0 12px;
}

.result-panel video {
  width: 100%;
  border-radius: 8px;
  border: 1px solid #d8c9b1;
  background: #111;
}

@media (max-width: 860px) {
  .digital-video-layout,
  .source-grid {
    grid-template-columns: 1fr;
  }
}
</style>
```

- [ ] **Step 2: Run frontend build**

Run:

```powershell
& 'D:\Program Files\nodejs\npm.cmd' run build
```

Expected: build succeeds.

- [ ] **Step 3: Commit page implementation**

```powershell
git add frontend/src/pages/DigitalHumanVideo.vue
git commit -m "feat: build digital human video page"
```

### Task 7: Documentation and Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README URLs**

Add this to the URL list in `README.md`:

```markdown
- Digital Human video page: `http://127.0.0.1:5173/digital-human-video`
- Digital Human video API: `http://127.0.0.1:8000/api/digital-human/videos/`
```

- [ ] **Step 2: Run backend tests**

Run from `D:\aiFire\backend`:

```powershell
$env:USE_SQLITE='1'; ..\.venv\Scripts\python.exe -m pytest tests/trends/test_digital_human_video.py tests/trends/test_digital_human_chat.py -q
```

Expected: PASS.

- [ ] **Step 3: Run Django system check**

Run from `D:\aiFire\backend`:

```powershell
$env:USE_SQLITE='1'; ..\.venv\Scripts\python.exe manage.py check
```

Expected: `System check identified no issues`.

- [ ] **Step 4: Run frontend build**

Run from `D:\aiFire\frontend`:

```powershell
& 'D:\Program Files\nodejs\npm.cmd' run build
```

Expected: build succeeds.

- [ ] **Step 5: Manual browser verification**

Start the app:

```powershell
powershell -ExecutionPolicy Bypass -File D:\aiFire\start-dev.ps1
```

Open:

```text
http://127.0.0.1:5173/digital-human-video
```

Verify:
- The top menu shows `热词洞察` and `数字人视频`
- `/digital-human-video` renders the new page
- The default form can be submitted
- If FFmpeg is missing, the UI shows the backend error clearly
- If FFmpeg is available, the page shows a video preview and `下载 mp4`

- [ ] **Step 6: Commit docs**

```powershell
git add README.md
git commit -m "docs: add digital human video URLs"
```

## Self-Review

1. **Spec coverage:** The plan covers the independent page, top menu navigation, default/upload audio, default/upload video, mp4 generation API, download API, media settings, error handling, and frontend build verification. It intentionally excludes history, queues, LiveTalking/Wav2Lip,素材库管理, user quotas, and TTS per the spec.
2. **Placeholder scan:** No unresolved markers or vague edge-case instructions remain. Each code-changing step includes concrete code or exact commands.
3. **Type consistency:** Frontend uses `script/audio_mode/video_mode/audio_file/video_file` through `FormData`; backend view passes those exact fields to `generate_digital_human_video`; response fields are `job_id/status/engine/video_url/download_url/message` throughout.
