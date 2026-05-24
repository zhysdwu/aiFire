# Alibaba Wanxiang Digital Human Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an Alibaba Wanxiang digital human video engine that can be selected from the existing admin-managed digital human configs.

**Architecture:** Keep the existing engine registry and add a focused Wanxiang client module. The adapter resolves local/default assets, creates audio for default mode with Alibaba TTS, prepares an avatar image from the selected video, submits a Wanxiang `wan2.2-s2v` task, polls it, downloads the generated MP4, and returns the same preview/download contract as the local engine.

**Tech Stack:** Django, DRF, requests, ffmpeg, Vue 3, Vite, pytest.

---

### Task 1: Add Engine Type and Public Label

**Files:**
- Modify: `backend/apps/trends/models.py`
- Create: `backend/apps/trends/migrations/0015_add_alibaba_wanxiang_engine.py`
- Modify: `backend/apps/trends/services/digital_human_engines.py`
- Test: `backend/tests/trends/test_digital_human_video.py`

- [ ] Add `alibaba_wanxiang` to `DigitalHumanEngineConfig.EngineType`.
- [ ] Add a migration that updates the model field choices.
- [ ] Add public label `Alibaba Wanxiang digital human`.
- [ ] Verify config list can expose the new engine without leaking API keys.

### Task 2: Build Wanxiang Client

**Files:**
- Create: `backend/apps/trends/services/alibaba_wanxiang_client.py`
- Test: `backend/tests/trends/test_digital_human_video.py`

- [ ] Implement config parsing with safe defaults for model, voice, timeout, poll interval, resolution, and API base URL.
- [ ] Implement local file upload through DashScope upload API.
- [ ] Implement default-mode TTS audio creation.
- [ ] Implement async Wanxiang task create, poll, and result extraction.
- [ ] Implement generated MP4 download to `MEDIA_ROOT/digital_human/outputs`.

### Task 3: Wire Adapter and Asset Preparation

**Files:**
- Modify: `backend/apps/trends/services/digital_human_engines.py`
- Modify: `backend/apps/trends/services/digital_human_video_service.py`
- Test: `backend/tests/trends/test_digital_human_video.py`

- [ ] Add helpers to extract an avatar frame image from the selected video with ffmpeg.
- [ ] Add `AlibabaWanxiangEngineAdapter`.
- [ ] Return clear Chinese errors for missing API key, missing ffmpeg, API failures, timeout, and missing result URL.
- [ ] Preserve the existing response shape: `status`, `engine`, `engine_config`, `video_url`, `download_url`, `message`.

### Task 4: Frontend Copy and Build

**Files:**
- Modify: `frontend/src/pages/DigitalHumanVideo.vue`

- [ ] Show a small helper note when the selected config is Alibaba Wanxiang, explaining that video is used as the avatar source and default audio will speak the script.
- [ ] Keep existing submit payload unchanged.
- [ ] Run the frontend build.

### Task 5: Verification

**Files:**
- Test: `backend/tests/trends/test_digital_human_video.py`

- [ ] Run the new failing tests first.
- [ ] Implement until the tests pass.
- [ ] Run `USE_SQLITE=1 python -m pytest backend/tests/trends/test_digital_human_video.py backend/tests/trends/test_digital_human_chat.py backend/tests/trends/test_ensure_daily_fetch.py -q`.
- [ ] Run `USE_SQLITE=1 python backend/manage.py check`.
- [ ] Run `npm run build` in `frontend`.
