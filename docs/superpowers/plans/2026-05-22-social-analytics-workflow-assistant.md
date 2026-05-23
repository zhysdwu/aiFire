# Social Analytics Workflow Assistant Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add cross-platform analytics, daily workflow status tracking, and an AI assistant panel on top of the existing TikTok / Instagram / Facebook hotword platform.

**Architecture:** Backend adds two lightweight audit models, focused services for analytics/workflow/assistant behavior, and three DRF endpoints. Frontend extends the existing hotwords page with compact comparison panels, workflow status, and an assistant panel without replacing the existing ranking workflow.

**Tech Stack:** Python, Django, Django REST Framework, MySQL, Vue 3, Vite, DeepSeek API

---

## File Structure

- **Models and migrations**
  - Modify: `backend/apps/trends/models.py`
  - Create: `backend/apps/trends/migrations/0010_dailyworkflowrun_assistantmessagelog.py`
- **Services**
  - Create: `backend/apps/trends/services/analytics.py`
  - Create: `backend/apps/trends/services/workflow.py`
  - Create: `backend/apps/trends/services/assistant.py`
- **Management commands**
  - Modify: `backend/apps/trends/management/commands/ensure_daily_fetch.py`
  - Modify: `backend/apps/trends/management/commands/run_daily_pipeline.py`
- **API**
  - Modify: `backend/apps/trends/api/urls.py`
  - Modify: `backend/apps/trends/api/views.py`
- **Frontend**
  - Modify: `frontend/src/api/client.js`
  - Modify: `frontend/src/pages/HotwordsList.vue`
- **Tests**
  - Create: `backend/tests/trends/test_analytics_workflow_assistant.py`

---

### Task 1: Add Workflow and Assistant Log Models

**Files:**
- Modify: `backend/apps/trends/models.py`
- Create: `backend/apps/trends/migrations/0010_dailyworkflowrun_assistantmessagelog.py`
- Test: `backend/tests/trends/test_analytics_workflow_assistant.py`

- [ ] **Step 1: Write failing model tests**

```python
import pytest
from django.utils import timezone

from apps.trends.models import AssistantMessageLog, DailyWorkflowRun, Platform


@pytest.mark.django_db
def test_daily_workflow_run_is_unique_per_platform_and_date():
    today = timezone.localdate()
    DailyWorkflowRun.objects.create(platform=Platform.TIKTOK, run_date=today)
    with pytest.raises(Exception):
        DailyWorkflowRun.objects.create(platform=Platform.TIKTOK, run_date=today)


@pytest.mark.django_db
def test_assistant_message_log_stores_question_and_answer():
    log = AssistantMessageLog.objects.create(
        platform=Platform.INSTAGRAM,
        question="Compare today",
        answer="Instagram is strong for visual hooks.",
        intent="platform_compare",
    )
    assert log.platform == Platform.INSTAGRAM
    assert log.intent == "platform_compare"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `$env:USE_SQLITE='1'; ..\.venv\Scripts\python.exe -m pytest tests/trends/test_analytics_workflow_assistant.py -q`  
Expected: FAIL because models do not exist.

- [ ] **Step 3: Add model classes**

```python
class WorkflowStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    RUNNING = "running", "Running"
    SUCCESS = "success", "Success"
    FAILED = "failed", "Failed"
    SKIPPED = "skipped", "Skipped"


class AssistantIntent(models.TextChoices):
    TREND_ANALYSIS = "trend_analysis", "Trend Analysis"
    PLATFORM_COMPARE = "platform_compare", "Platform Compare"
    TITLE_REFINE = "title_refine", "Title Refine"
    GENERAL = "general", "General"


class DailyWorkflowRun(models.Model):
    platform = models.CharField(max_length=16, choices=Platform.choices)
    run_date = models.DateField()
    fetch_status = models.CharField(max_length=16, choices=WorkflowStatus.choices, default=WorkflowStatus.PENDING)
    extract_status = models.CharField(max_length=16, choices=WorkflowStatus.choices, default=WorkflowStatus.PENDING)
    recommend_status = models.CharField(max_length=16, choices=WorkflowStatus.choices, default=WorkflowStatus.PENDING)
    last_message = models.CharField(max_length=255, blank=True, default="")
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("platform", "run_date")]


class AssistantMessageLog(models.Model):
    platform = models.CharField(max_length=16, choices=Platform.choices, default=Platform.TIKTOK)
    phrase = models.ForeignKey("Phrase", null=True, blank=True, on_delete=models.SET_NULL, related_name="assistant_logs")
    question = models.TextField()
    answer = models.TextField()
    intent = models.CharField(max_length=32, choices=AssistantIntent.choices, default=AssistantIntent.GENERAL)
    created_by = models.ForeignKey("auth.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="assistant_message_logs")
    created_at = models.DateTimeField(auto_now_add=True)
```

- [ ] **Step 4: Generate and apply migration**

Run: `..\.venv\Scripts\python.exe manage.py makemigrations trends`  
Run: `..\.venv\Scripts\python.exe manage.py migrate`  
Expected: Migration is created and applied.

- [ ] **Step 5: Run model tests**

Run: `$env:USE_SQLITE='1'; ..\.venv\Scripts\python.exe -m pytest tests/trends/test_analytics_workflow_assistant.py -q`  
Expected: PASS for the model tests.

---

### Task 2: Add Analytics Service and API

**Files:**
- Create: `backend/apps/trends/services/analytics.py`
- Modify: `backend/apps/trends/api/views.py`
- Modify: `backend/apps/trends/api/urls.py`
- Test: `backend/tests/trends/test_analytics_workflow_assistant.py`

- [ ] **Step 1: Add failing analytics API test**

```python
@pytest.mark.django_db
def test_analytics_overview_returns_all_social_platforms(api_client):
    response = api_client.get("/api/analytics/overview/")
    assert response.status_code == 200
    platforms = {item["platform"] for item in response.data["platforms"]}
    assert platforms == {"tiktok", "instagram", "facebook"}
    assert "comparison" in response.data
```

- [ ] **Step 2: Run test to verify failure**

Run: `$env:USE_SQLITE='1'; ..\.venv\Scripts\python.exe -m pytest tests/trends/test_analytics_workflow_assistant.py::test_analytics_overview_returns_all_social_platforms -q`  
Expected: FAIL because endpoint does not exist.

- [ ] **Step 3: Implement analytics service**

```python
from django.db.models import Avg

from apps.trends.models import Phrase, Platform, RiskLevel, Window


SOCIAL_PLATFORMS = [Platform.TIKTOK, Platform.INSTAGRAM, Platform.FACEBOOK]


def build_analytics_overview() -> dict:
    rows = []
    for platform in SOCIAL_PLATFORMS:
        qs = Phrase.objects.filter(platform=platform, is_deleted=False).exclude(risk_level=RiskLevel.BLOCKED)
        avg = qs.filter(metrics__window=Window.H24).aggregate(value=Avg("metrics__heat_score"))["value"] or 0
        top_keywords = list(qs.order_by("-last_seen_at").values_list("text", flat=True)[:5])
        last_updated = qs.order_by("-last_seen_at").values_list("last_seen_at", flat=True).first()
        rows.append({
            "platform": platform,
            "total_phrases": qs.count(),
            "avg_heat_score": round(float(avg), 2),
            "top_keywords": top_keywords,
            "last_updated_at": last_updated,
        })

    highest_heat = max(rows, key=lambda item: item["avg_heat_score"], default=None)
    most_keywords = max(rows, key=lambda item: item["total_phrases"], default=None)
    return {
        "platforms": rows,
        "comparison": {
            "highest_heat_platform": highest_heat["platform"] if highest_heat else "",
            "most_keywords_platform": most_keywords["platform"] if most_keywords else "",
        },
    }
```

- [ ] **Step 4: Add API view and URL**

```python
class AnalyticsOverviewView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response(build_analytics_overview())
```

URL:

```python
path("analytics/overview/", AnalyticsOverviewView.as_view(), name="analytics-overview")
```

- [ ] **Step 5: Run analytics test**

Run: `$env:USE_SQLITE='1'; ..\.venv\Scripts\python.exe -m pytest tests/trends/test_analytics_workflow_assistant.py::test_analytics_overview_returns_all_social_platforms -q`  
Expected: PASS.

---

### Task 3: Add Workflow Service and API

**Files:**
- Create: `backend/apps/trends/services/workflow.py`
- Modify: `backend/apps/trends/api/views.py`
- Modify: `backend/apps/trends/api/urls.py`
- Modify: `backend/apps/trends/management/commands/ensure_daily_fetch.py`
- Modify: `backend/apps/trends/management/commands/run_daily_pipeline.py`
- Test: `backend/tests/trends/test_analytics_workflow_assistant.py`

- [ ] **Step 1: Add failing workflow API test**

```python
@pytest.mark.django_db
def test_workflow_status_returns_today_rows(api_client):
    response = api_client.get("/api/workflow/status/")
    assert response.status_code == 200
    assert len(response.data["runs"]) == 3
    assert {item["platform"] for item in response.data["runs"]} == {"tiktok", "instagram", "facebook"}
```

- [ ] **Step 2: Run test to verify failure**

Run: `$env:USE_SQLITE='1'; ..\.venv\Scripts\python.exe -m pytest tests/trends/test_analytics_workflow_assistant.py::test_workflow_status_returns_today_rows -q`  
Expected: FAIL because endpoint does not exist.

- [ ] **Step 3: Implement workflow service**

```python
from django.utils import timezone

from apps.trends.models import DailyWorkflowRun, Platform, WorkflowStatus

SOCIAL_PLATFORMS = [Platform.TIKTOK, Platform.INSTAGRAM, Platform.FACEBOOK]


def get_or_create_today_run(platform: str) -> DailyWorkflowRun:
    run, _ = DailyWorkflowRun.objects.get_or_create(platform=platform, run_date=timezone.localdate())
    return run


def mark_step(platform: str, step: str, status: str, message: str = "") -> DailyWorkflowRun:
    run = get_or_create_today_run(platform)
    setattr(run, f"{step}_status", status)
    if status == WorkflowStatus.RUNNING and not run.started_at:
        run.started_at = timezone.now()
    if status in {WorkflowStatus.SUCCESS, WorkflowStatus.FAILED, WorkflowStatus.SKIPPED}:
        run.finished_at = timezone.now()
    run.last_message = message[:255]
    run.save()
    return run


def build_today_workflow_status() -> dict:
    runs = [get_or_create_today_run(platform) for platform in SOCIAL_PLATFORMS]
    return {
        "date": timezone.localdate().isoformat(),
        "runs": [
            {
                "platform": run.platform,
                "fetch_status": run.fetch_status,
                "extract_status": run.extract_status,
                "recommend_status": run.recommend_status,
                "last_message": run.last_message,
                "updated_at": run.updated_at,
            }
            for run in runs
        ],
    }
```

- [ ] **Step 4: Add API view and URL**

```python
class WorkflowStatusView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response(build_today_workflow_status())
```

URL:

```python
path("workflow/status/", WorkflowStatusView.as_view(), name="workflow-status")
```

- [ ] **Step 5: Wire management commands**

In `ensure_daily_fetch.py`, when a platform is skipped:

```python
mark_step(platform, "fetch", WorkflowStatus.SKIPPED, "Already fetched today")
```

Before running a platform:

```python
mark_step(platform, "fetch", WorkflowStatus.RUNNING, "Starting fetch")
```

After success:

```python
mark_step(platform, "fetch", WorkflowStatus.SUCCESS, "Fetch completed")
```

After failure:

```python
mark_step(platform, "fetch", WorkflowStatus.FAILED, "Fetch failed")
```

- [ ] **Step 6: Run workflow tests**

Run: `$env:USE_SQLITE='1'; ..\.venv\Scripts\python.exe -m pytest tests/trends/test_analytics_workflow_assistant.py -q`  
Expected: PASS for workflow tests.

---

### Task 4: Add Assistant Service and API

**Files:**
- Create: `backend/apps/trends/services/assistant.py`
- Modify: `backend/apps/trends/api/views.py`
- Modify: `backend/apps/trends/api/urls.py`
- Test: `backend/tests/trends/test_analytics_workflow_assistant.py`

- [ ] **Step 1: Add failing assistant fallback test**

```python
@pytest.mark.django_db
def test_assistant_chat_returns_fallback_without_api_key(api_client, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    response = api_client.post("/api/assistant/chat/", {"platform": "tiktok", "question": "Compare platforms"}, format="json")
    assert response.status_code == 200
    assert response.data["intent"] in {"platform_compare", "general"}
    assert response.data["answer"]
```

- [ ] **Step 2: Run test to verify failure**

Run: `$env:USE_SQLITE='1'; ..\.venv\Scripts\python.exe -m pytest tests/trends/test_analytics_workflow_assistant.py::test_assistant_chat_returns_fallback_without_api_key -q`  
Expected: FAIL because endpoint does not exist.

- [ ] **Step 3: Implement assistant service**

```python
from apps.trends.models import AssistantIntent, AssistantMessageLog, Phrase, Platform
from apps.trends.services.analytics import build_analytics_overview
from apps.trends.services.deepseek_client import DeepSeekClient


def classify_intent(question: str) -> str:
    q = question.lower()
    if "compare" in q or "对比" in q:
        return AssistantIntent.PLATFORM_COMPARE
    if "title" in q or "标题" in q:
        return AssistantIntent.TITLE_REFINE
    if "why" in q or "popular" in q or "为什么" in q:
        return AssistantIntent.TREND_ANALYSIS
    return AssistantIntent.GENERAL


def fallback_answer(platform: str, question: str, phrase: Phrase | None = None) -> str:
    target = phrase.text if phrase else platform
    return f"当前可以围绕 {target} 做选题判断：优先关注热度高、表达清晰、适合转化为标题的关键词。"


def answer_assistant_question(platform: str, question: str, phrase_id: int | None, user=None) -> dict:
    phrase = Phrase.objects.filter(id=phrase_id).first() if phrase_id else None
    intent = classify_intent(question)
    answer = fallback_answer(platform, question, phrase)
    try:
        client = DeepSeekClient.from_env()
        overview = build_analytics_overview()
        payload = client.chat_json(
            system="You are a social trend analyst. Return JSON with answer and suggestions.",
            user=f"PLATFORM={platform}\nPHRASE={phrase.text if phrase else ''}\nQUESTION={question}\nOVERVIEW={overview}",
        )
        answer = (payload.get("answer") or answer).strip()
        suggestions = payload.get("suggestions") or ["Compare platforms", "Generate title variants"]
    except Exception:
        suggestions = ["对比平台表现", "生成标题变体"]

    AssistantMessageLog.objects.create(platform=platform, phrase=phrase, question=question, answer=answer, intent=intent, created_by=user if getattr(user, "is_authenticated", False) else None)
    return {"intent": intent, "answer": answer, "suggestions": suggestions}
```

- [ ] **Step 4: Add API view and URL**

```python
class AssistantChatView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        question = (request.data.get("question") or "").strip()
        if len(question) < 2:
            return Response({"detail": "Question is too short"}, status=400)
        platform = (request.data.get("platform") or Platform.TIKTOK).strip().lower()
        phrase_id = request.data.get("phrase_id")
        return Response(answer_assistant_question(platform, question, phrase_id, request.user))
```

URL:

```python
path("assistant/chat/", AssistantChatView.as_view(), name="assistant-chat")
```

- [ ] **Step 5: Run assistant tests**

Run: `$env:USE_SQLITE='1'; ..\.venv\Scripts\python.exe -m pytest tests/trends/test_analytics_workflow_assistant.py -q`  
Expected: PASS.

---

### Task 5: Frontend Analytics, Workflow, and Assistant UI

**Files:**
- Modify: `frontend/src/api/client.js`
- Modify: `frontend/src/pages/HotwordsList.vue`

- [ ] **Step 1: Add API client methods**

```javascript
export async function fetchAnalyticsOverview() {
  const response = await fetch("/api/analytics/overview/", { credentials: "same-origin" });
  if (!response.ok) throw new Error("获取分析概览失败");
  return response.json();
}

export async function fetchWorkflowStatus() {
  const response = await fetch("/api/workflow/status/", { credentials: "same-origin" });
  if (!response.ok) throw new Error("获取工作流状态失败");
  return response.json();
}

export async function sendAssistantQuestion({ platform, phraseId, question }) {
  const response = await fetch("/api/assistant/chat/", {
    method: "POST",
    credentials: "same-origin",
    headers: csrfHeaders(),
    body: JSON.stringify({ platform, phrase_id: phraseId, question }),
  });
  if (!response.ok) throw new Error("AI助手暂时不可用");
  return response.json();
}
```

- [ ] **Step 2: Load overview and workflow on hotwords page**

```javascript
const analytics = ref(null);
const workflow = ref(null);

const [phrasePayload, summaryPayload, analyticsPayload, workflowPayload] = await Promise.all([
  fetchPhrases({
    window: windowValue.value,
    sort: sortValue.value,
    q: query.value,
    page: page.value,
    platform: platformValue.value,
  }),
  fetchPlatformSummary(platformValue.value),
  fetchAnalyticsOverview(),
  fetchWorkflowStatus(),
]);
```

- [ ] **Step 3: Add analytics comparison UI**

Add compact platform rows with:

- platform label
- `total_phrases`
- `avg_heat_score`
- top keyword chips

- [ ] **Step 4: Add workflow status strip**

Add three columns for TikTok, Instagram, Facebook, each showing:

- fetch status
- extract status
- recommend status

- [ ] **Step 5: Add assistant panel**

Add:

- textarea input
- submit button
- response area
- suggestions chips

Use current `platformValue` as default context.

- [ ] **Step 6: Build frontend**

Run: `npm.cmd run build` from `D:\aiFire\frontend`  
Expected: PASS.

---

### Task 6: Full Verification and Docs

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Run backend checks**

Run: `..\.venv\Scripts\python.exe manage.py check` from `D:\aiFire\backend`  
Expected: `System check identified no issues`.

- [ ] **Step 2: Run backend tests**

Run: `$env:USE_SQLITE='1'; ..\.venv\Scripts\python.exe -m pytest tests/trends -q` from `D:\aiFire\backend`  
Expected: PASS.

- [ ] **Step 3: Run frontend build**

Run: `npm.cmd run build` from `D:\aiFire\frontend`  
Expected: PASS.

- [ ] **Step 4: Update README endpoints**

Add:

```markdown
- Analytics overview: `http://127.0.0.1:8000/api/analytics/overview/`
- Workflow status: `http://127.0.0.1:8000/api/workflow/status/`
- Assistant chat: `http://127.0.0.1:8000/api/assistant/chat/`
```

- [ ] **Step 5: Commit**

```bash
git add README.md backend frontend docs/superpowers
git commit -m "feat: add social analytics workflow and assistant"
```

---

## Self-Review

Spec coverage:

- Cross-platform analytics: Task 2 and Task 5.
- Workflow status: Task 1, Task 3, and Task 5.
- AI assistant: Task 1, Task 4, and Task 5.
- Existing features preserved: Task 6 full test and build checks.

No placeholders are left in implementation steps. Function names and endpoint paths are consistent across backend, tests, and frontend.
