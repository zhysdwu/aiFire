# Homepage Digital Human (LiveTalking + DeepSeek) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在首页新增悬浮数字人入口，通过单一聚合接口实现“文本提问 -> DeepSeek回答（结论+3要点）-> LiveTalking播报”的稳定链路。

**Architecture:** 前端只调用 `POST /api/digital-human/chat/`，后端在新聚合服务中完成参数校验、意图识别、DeepSeek调用、日志落库与LiveTalking触发。文本回答是主链路，LiveTalking失败不阻断主链路，并通过 `trace_id` 提供可追踪性。

**Tech Stack:** Django, Django REST Framework, Vue 3, Vite, DeepSeek API, LiveTalking

---

## File Structure

- **Backend API**
  - Create: `backend/apps/trends/api/digital_human_views.py`
  - Modify: `backend/apps/trends/api/urls.py`
- **Backend Services**
  - Create: `backend/apps/trends/services/digital_human_service.py`
  - Create: `backend/apps/trends/services/assistant_core.py`
  - Create: `backend/apps/trends/services/livetalking_client.py`
- **Backend Models / Migration**
  - Modify: `backend/apps/trends/models.py`
  - Create: `backend/apps/trends/migrations/0012_digitalhumansessionlog.py`
- **Backend Tests**
  - Create: `backend/tests/trends/test_digital_human_chat.py`
- **Frontend**
  - Create: `frontend/src/components/FloatingDigitalHuman.vue`
  - Modify: `frontend/src/api/client.js`
  - Modify: `frontend/src/pages/HotwordsList.vue`

### Task 1: 新增聚合聊天接口的失败测试

**Files:**
- Create: `backend/tests/trends/test_digital_human_chat.py`

- [ ] **Step 1: 写失败测试（接口存在性与返回结构）**

```python
import pytest


@pytest.mark.django_db
def test_digital_human_chat_returns_required_fields(api_client, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    response = api_client.post(
        "/api/digital-human/chat/",
        {"platform": "tiktok", "question": "今天适合做什么内容方向"},
        format="json",
    )
    assert response.status_code == 200
    data = response.data
    assert "answer" in data
    assert "highlights" in data
    assert "intent" in data
    assert "provider" in data
    assert "livetalking" in data
    assert "trace_id" in data
```

- [ ] **Step 2: 运行测试确认失败**

Run: `$env:USE_SQLITE='1'; ..\.venv\Scripts\python.exe -m pytest tests/trends/test_digital_human_chat.py::test_digital_human_chat_returns_required_fields -q`  
Expected: FAIL（路由不存在或 404）

- [ ] **Step 3: 提交测试基线**

```bash
git add backend/tests/trends/test_digital_human_chat.py
git commit -m "test: add failing digital human chat contract test"
```

### Task 2: 实现后端聚合服务与接口

**Files:**
- Create: `backend/apps/trends/services/assistant_core.py`
- Create: `backend/apps/trends/services/livetalking_client.py`
- Create: `backend/apps/trends/services/digital_human_service.py`
- Create: `backend/apps/trends/api/digital_human_views.py`
- Modify: `backend/apps/trends/api/urls.py`

- [ ] **Step 1: 实现 DeepSeek 输出规范化核心**

```python
# backend/apps/trends/services/assistant_core.py
from apps.trends.models import Platform


def classify_intent(question: str) -> str:
    q = (question or "").lower()
    if "对比" in q or "compare" in q:
        return "platform_compare"
    if "标题" in q or "title" in q:
        return "title_refine"
    return "trend_analysis"


def fallback_brief_answer(platform: str, question: str) -> tuple[str, list[str]]:
    label = platform if platform in {Platform.TIKTOK, Platform.INSTAGRAM, Platform.FACEBOOK, Platform.YOUTUBE} else Platform.TIKTOK
    answer = f"结论：{label} 当前适合做强场景、强情绪、强钩子的内容方向。"
    highlights = [
        "优先选择近24小时热度上升且表达具体的关键词。",
        "标题结构建议采用“结果+对象+时效”格式。",
        "先发3条小样本内容，按反馈快速迭代标题。",
    ]
    return answer, highlights
```

- [ ] **Step 2: 实现 LiveTalking 客户端封装**

```python
# backend/apps/trends/services/livetalking_client.py
import requests


def trigger_livetalking_speak(text: str, trace_id: str) -> dict:
    try:
        response = requests.post(
            "http://127.0.0.1:8010/api/speak",
            json={"text": text, "trace_id": trace_id},
            timeout=3,
        )
        if response.ok:
            return {"status": "queued", "message": "播报任务已提交"}
        return {"status": "failed", "message": f"播报服务返回 {response.status_code}"}
    except Exception as exc:
        return {"status": "failed", "message": str(exc)}
```

- [ ] **Step 3: 实现聚合服务编排**

```python
# backend/apps/trends/services/digital_human_service.py
import uuid
from apps.trends.models import Platform
from apps.trends.services.assistant import answer_assistant_question
from apps.trends.services.assistant_core import classify_intent, fallback_brief_answer
from apps.trends.services.livetalking_client import trigger_livetalking_speak


def normalize_platform(value: str) -> str:
    platform = (value or Platform.TIKTOK).strip().lower()
    return platform if platform in {Platform.TIKTOK, Platform.INSTAGRAM, Platform.FACEBOOK, Platform.YOUTUBE} else Platform.TIKTOK


def run_digital_human_chat(platform: str, question: str, phrase_id=None, user=None, session_id=None) -> dict:
    trace_id = str(uuid.uuid4())
    platform = normalize_platform(platform)
    intent = classify_intent(question)
    payload = answer_assistant_question(platform, question, phrase_id, user)
    answer = payload.get("answer") or ""
    provider = "deepseek" if payload.get("ai_status") == "deepseek" else "fallback"
    if not answer:
        answer, highlights = fallback_brief_answer(platform, question)
    else:
        highlights = payload.get("suggestions")[:3] if payload.get("suggestions") else fallback_brief_answer(platform, question)[1]
    livetalking = trigger_livetalking_speak(answer, trace_id)
    return {
        "answer": answer,
        "highlights": highlights,
        "intent": intent,
        "provider": provider,
        "livetalking": livetalking,
        "trace_id": trace_id,
    }
```

- [ ] **Step 4: 暴露 API 视图和路由**

```python
# backend/apps/trends/api/digital_human_views.py
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.trends.services.digital_human_service import run_digital_human_chat


class DigitalHumanChatView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        question = (request.data.get("question") or "").strip()
        if len(question) < 2:
            return Response({"detail": "问题至少2个字符"}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            run_digital_human_chat(
                platform=request.data.get("platform"),
                question=question,
                phrase_id=request.data.get("phrase_id"),
                user=request.user,
                session_id=request.data.get("session_id"),
            )
        )
```

```python
# backend/apps/trends/api/urls.py
from apps.trends.api.digital_human_views import DigitalHumanChatView
path("digital-human/chat/", DigitalHumanChatView.as_view(), name="digital-human-chat"),
```

- [ ] **Step 5: 运行测试确认通过**

Run: `$env:USE_SQLITE='1'; ..\.venv\Scripts\python.exe -m pytest tests/trends/test_digital_human_chat.py -q`  
Expected: PASS

- [ ] **Step 6: 提交后端聚合接口**

```bash
git add backend/apps/trends/api/digital_human_views.py backend/apps/trends/api/urls.py backend/apps/trends/services/assistant_core.py backend/apps/trends/services/livetalking_client.py backend/apps/trends/services/digital_human_service.py
git commit -m "feat: add digital human aggregate chat endpoint"
```

### Task 3: 增加聚合会话日志模型

**Files:**
- Modify: `backend/apps/trends/models.py`
- Create: `backend/apps/trends/migrations/0012_digitalhumansessionlog.py`
- Modify: `backend/apps/trends/services/digital_human_service.py`
- Modify: `backend/tests/trends/test_digital_human_chat.py`

- [ ] **Step 1: 写失败测试（trace_id 落库）**

```python
from apps.trends.models import DigitalHumanSessionLog


@pytest.mark.django_db
def test_digital_human_chat_persists_session_log(api_client, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    response = api_client.post("/api/digital-human/chat/", {"platform": "tiktok", "question": "给我方向"}, format="json")
    assert response.status_code == 200
    trace_id = response.data["trace_id"]
    assert DigitalHumanSessionLog.objects.filter(trace_id=trace_id).exists()
```

- [ ] **Step 2: 运行失败测试**

Run: `$env:USE_SQLITE='1'; ..\.venv\Scripts\python.exe -m pytest tests/trends/test_digital_human_chat.py::test_digital_human_chat_persists_session_log -q`  
Expected: FAIL（模型不存在）

- [ ] **Step 3: 增加模型与迁移**

```python
# backend/apps/trends/models.py
class DigitalHumanSessionLog(models.Model):
    platform = models.CharField(max_length=16, choices=Platform.choices, default=Platform.TIKTOK)
    question = models.TextField()
    answer = models.TextField(blank=True, default="")
    intent = models.CharField(max_length=32, blank=True, default="")
    provider = models.CharField(max_length=32, blank=True, default="")
    trace_id = models.CharField(max_length=64, unique=True)
    session_id = models.CharField(max_length=64, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
```

- [ ] **Step 4: 在聚合服务里写日志**

```python
from apps.trends.models import DigitalHumanSessionLog

DigitalHumanSessionLog.objects.create(
    platform=platform,
    question=question,
    answer=answer,
    intent=intent,
    provider=provider,
    trace_id=trace_id,
    session_id=session_id or "",
)
```

- [ ] **Step 5: 运行迁移与测试**

Run: `..\.venv\Scripts\python.exe manage.py makemigrations trends`  
Expected: 生成 `0012_digitalhumansessionlog.py`

Run: `..\.venv\Scripts\python.exe manage.py migrate`  
Expected: OK

Run: `$env:USE_SQLITE='1'; ..\.venv\Scripts\python.exe -m pytest tests/trends/test_digital_human_chat.py -q`  
Expected: PASS

- [ ] **Step 6: 提交日志能力**

```bash
git add backend/apps/trends/models.py backend/apps/trends/migrations/0012_digitalhumansessionlog.py backend/apps/trends/services/digital_human_service.py backend/tests/trends/test_digital_human_chat.py
git commit -m "feat: persist digital human session logs with trace id"
```

### Task 4: 前端接入悬浮数字人组件

**Files:**
- Create: `frontend/src/components/FloatingDigitalHuman.vue`
- Modify: `frontend/src/api/client.js`
- Modify: `frontend/src/pages/HotwordsList.vue`

- [ ] **Step 1: 写前端 API 调用**

```javascript
// frontend/src/api/client.js
export async function digitalHumanChat({ platform, question, phraseId, sessionId }) {
  const response = await fetch("/api/digital-human/chat/", {
    method: "POST",
    credentials: "same-origin",
    headers: csrfHeaders(),
    body: JSON.stringify({
      platform,
      question,
      phrase_id: phraseId ?? null,
      session_id: sessionId ?? "",
    }),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || "数字人暂时不可用");
  }
  return response.json();
}
```

- [ ] **Step 2: 实现悬浮组件**

```vue
<!-- frontend/src/components/FloatingDigitalHuman.vue -->
<script setup>
import { ref } from "vue";
import { digitalHumanChat } from "../api/client";
const props = defineProps({ platform: { type: String, default: "tiktok" } });
const open = ref(false);
const question = ref("");
const answer = ref("");
const highlights = ref([]);
const livetalking = ref({ status: "", message: "" });
const loading = ref(false);
const error = ref("");
const sessionId = `dh-${Date.now()}`;
async function ask() {
  const q = question.value.trim();
  if (q.length < 2) {
    error.value = "请输入至少2个字符的问题";
    return;
  }
  loading.value = true;
  error.value = "";
  try {
    const payload = await digitalHumanChat({ platform: props.platform, question: q, sessionId });
    answer.value = payload.answer || "";
    highlights.value = payload.highlights || [];
    livetalking.value = payload.livetalking || { status: "", message: "" };
  } catch (err) {
    error.value = err.message || "数字人调用失败";
  } finally {
    loading.value = false;
  }
}
</script>
```

- [ ] **Step 3: 首页挂载组件并移除旧数字人块**

```vue
<!-- frontend/src/pages/HotwordsList.vue -->
<script setup>
import FloatingDigitalHuman from "../components/FloatingDigitalHuman.vue";
</script>
<template>
  <FloatingDigitalHuman :platform="platformValue" />
</template>
```

- [ ] **Step 4: 运行前端构建验证**

Run: `npm.cmd run build`（workdir: `D:\aiFire\frontend`）  
Expected: build successful

- [ ] **Step 5: 提交前端接入**

```bash
git add frontend/src/components/FloatingDigitalHuman.vue frontend/src/api/client.js frontend/src/pages/HotwordsList.vue
git commit -m "feat: add floating homepage digital human panel"
```

### Task 5: 回归验证与文档更新

**Files:**
- Modify: `README.md`

- [ ] **Step 1: 运行后端测试集**

Run: `$env:USE_SQLITE='1'; ..\.venv\Scripts\python.exe -m pytest tests/trends -q`（workdir: `D:\aiFire\backend`）  
Expected: PASS

- [ ] **Step 2: 运行 Django 自检**

Run: `..\.venv\Scripts\python.exe manage.py check`（workdir: `D:\aiFire\backend`）  
Expected: `System check identified no issues`

- [ ] **Step 3: 更新 README 接口说明**

```markdown
- Digital Human chat: `http://127.0.0.1:8000/api/digital-human/chat/`
```

- [ ] **Step 4: 提交验证与文档**

```bash
git add README.md
git commit -m "docs: add digital human chat endpoint usage"
```

## Self-Review

1. **Spec coverage:** 已覆盖悬浮入口、聚合接口、DeepSeek简洁回答、LiveTalking播报、降级、trace_id日志、测试与验收。
2. **Placeholder scan:** 计划中无 `TODO/TBD/implement later` 占位符。
3. **Type consistency:** 接口字段在前后端统一使用 `platform/question/phrase_id/session_id/trace_id/livetalking`。
