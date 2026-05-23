# AI 热词合法性检测 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 每日管道 extract 之后用 DeepSeek 批量检测新热词合法性，将存疑词推入 `pending_review` 状态供管理员审核。

**Architecture:** RiskLevel 新增 PENDING_REVIEW 等级；risk.py 新增 ai_batch_assess() 批量调用 DeepSeek；run_daily_pipeline 在 extract 末尾调用检测；Django Admin 新增审核 action；前端 API 排除 pending_review。

**Tech Stack:** Django + DRF + DeepSeek API，无新增依赖。

---

### Task 1: 数据库 Migration — 新增 RiskLevel

**Files:**
- Modify: `D:\aiFire\backend\apps\trends\models.py`
- Create: migration 文件（Django 自动生成）

- [ ] **Step 1: 修改 models.py 的 RiskLevel**

将 `RiskLevel` 类修改为：

```python
class RiskLevel(models.TextChoices):
    LOW = "low", "Low"
    MEDIUM = "medium", "Medium"
    HIGH = "high", "High"
    BLOCKED = "blocked", "Blocked"
    PENDING_REVIEW = "pending_review", "Pending Review"
```

- [ ] **Step 2: 生成并运行 migration**

```powershell
D:\aiFire\.venv\Scripts\python.exe D:\aiFire\backend\manage.py makemigrations trends
D:\aiFire\.venv\Scripts\python.exe D:\aiFire\backend\manage.py migrate
```

Expected: 生成 migration `0013_alter_risk_level_choices.py`，迁移成功。

---

### Task 2: AI 批量检测服务（risk.py）

**Files:**
- Modify: `D:\aiFire\backend\apps\trends\services\risk.py`

- [ ] **Step 1: 添加 ai_batch_assess() 函数**

在 risk.py 末尾添加（保留原有 regex 检测函数不变）：

```python
import json

from apps.trends.services.deepseek_client import DeepSeekClient


BATCH_SIZE = 30

AI_REVIEW_SYSTEM_PROMPT = (
    "You are a content safety auditor. Review the following English keywords and classify each.\n"
    "Check for these violation categories:\n"
    "- Political sensitivity, hate speech, violent extremism\n"
    "- Adult/sexual content\n"
    "- Drugs/controlled substances\n"
    "- Trademark/brand infringement\n\n"
    "For each keyword, output:\n"
    '- "SAFE" if no issues\n'
    '- "REVIEW" if uncertain or borderline (needs human review)\n'
    '- "BLOCK" if clearly violating\n'
    'Return a JSON object: {"keyword1": {"verdict": "SAFE|REVIEW|BLOCK", "reason": "brief reason"}, ...}\n'
    'Only return the JSON object, no other text.'
)


def ai_batch_assess(keywords: list[str]) -> dict[str, dict]:
    """批量调用 DeepSeek 检测关键词合法性。

    Returns:
        {"keyword": {"verdict": "SAFE|REVIEW|BLOCK", "reason": "..."}, ...}
    失败时返回空 dict。
    """
    if not keywords:
        return {}

    results: dict[str, dict] = {}

    for i in range(0, len(keywords), BATCH_SIZE):
        batch = keywords[i : i + BATCH_SIZE]
        try:
            client = DeepSeekClient.from_env()
            user_prompt = "Keywords to review:\n" + "\n".join(
                f"{idx + 1}. \"{kw}\"" for idx, kw in enumerate(batch)
            )
            payload = client.chat_json(system=AI_REVIEW_SYSTEM_PROMPT, user=user_prompt)
            if isinstance(payload, dict):
                for kw in batch:
                    item = payload.get(kw, {})
                    verdict = (item.get("verdict") or "SAFE").upper()
                    reason = (item.get("reason") or "")[:200]
                    if verdict not in {"SAFE", "REVIEW", "BLOCK"}:
                        verdict = "SAFE"
                    results[kw] = {"verdict": verdict, "reason": reason}
        except Exception:
            # API 不可用时整个批次标记为 SAFE（保守策略，不阻塞管道）
            for kw in batch:
                results[kw] = {"verdict": "SAFE", "reason": "AI unavailable, defaulting to safe"}
    return results


def apply_ai_verdict(phrase_text: str, verdict_data: dict, current_risk: str) -> str:
    """根据 AI 判定结果更新风险等级。

    仅对当前 risk_level=low 的词应用 AI 判定。
    已标记为 medium/high/blocked 的保持原值（规则引擎优先）。
    """
    if current_risk not in {RiskLevel.LOW, RiskLevel.PENDING_REVIEW}:
        return current_risk

    verdict = verdict_data.get("verdict", "SAFE").upper()
    if verdict == "BLOCK":
        return RiskLevel.BLOCKED
    elif verdict == "REVIEW":
        return RiskLevel.PENDING_REVIEW
    return RiskLevel.LOW
```

- [ ] **Step 2: 运行已有测试确保不破坏**

```powershell
D:\aiFire\.venv\Scripts\python.exe -m pytest D:\aiFire\backend\tests\ -v --tb=short 2>&1 | Select-Object -Last 20
```

---

### Task 3: 管道集成 — extract 末尾调用 AI 检测

**Files:**
- Modify: `D:\aiFire\backend\apps\trends\management\commands\run_daily_pipeline.py`

- [ ] **Step 1: 在 extract 逻辑末尾插入 AI 检测**

在 `run_daily_pipeline.py` 中，找到 extract 步骤处理完毕后、recommend 步骤之前的位置。大致在短语创建循环之后、`_normalize_all_h24_scores()` 之前。

在合适位置插入：

```python
# ── AI 合法性批量检测 ──
from apps.trends.services.risk import ai_batch_assess, apply_ai_verdict

if client and phrases:
    # 收集当日新提取的 low 风险词
    pending_phrases = list(
        Phrase.objects.filter(
            platform=platform,
            is_deleted=False,
            risk_level=RiskLevel.LOW,
            last_seen_at=now,
        ).values_list("text", flat=True)
    )
    if pending_phrases:
        self.stdout.write(f"AI 合法性检测：{len(pending_phrases)} 个词")
        try:
            verdicts = ai_batch_assess(pending_phrases)
            for p_text in pending_phrases:
                verdict_data = verdicts.get(p_text, {})
                if verdict_data.get("verdict", "SAFE") != "SAFE":
                    try:
                        p = Phrase.objects.get(text=p_text, platform=platform, is_deleted=False)
                        new_risk = apply_ai_verdict(p_text, verdict_data, p.risk_level)
                        if new_risk != p.risk_level:
                            p.risk_level = new_risk
                            p.save(update_fields=["risk_level"])
                            self.stdout.write(f"  {p_text} → {new_risk} ({verdict_data.get('reason', '')})")
                    except Phrase.DoesNotExist:
                        pass
            reviewed_count = sum(1 for v in verdicts.values() if v.get("verdict") != "SAFE")
            self.stdout.write(self.style.SUCCESS(f"AI 检测完成：{reviewed_count} 个需关注"))
        except Exception as exc:
            self.stdout.write(self.style.WARNING(f"AI 检测跳过：{exc}"))
```

- [ ] **Step 2: 验证语法**

```powershell
D:\aiFire\.venv\Scripts\python.exe -c "import ast; ast.parse(open(r'D:\aiFire\backend\apps\trends\management\commands\run_daily_pipeline.py').read()); print('OK')"
```

---

### Task 4: Django Admin 审核 Action

**Files:**
- Modify: `D:\aiFire\backend\apps\trends\admin.py`

- [ ] **Step 1: 在 PhraseAdmin 新增审核 actions**

在 `PhraseAdmin` 类的 `actions` 列表和类体中添加：

```python
# 修改 actions 列表
actions = ["soft_delete_selected", "approve_review_selected", "block_review_selected"]

# 在 soft_delete_selected 方法之后添加：
@admin.action(description="审核通过（→安全）")
def approve_review_selected(self, request, queryset):
    count = queryset.filter(risk_level="pending_review").update(risk_level="low")
    self.message_user(request, f"已通过 {count} 个待审核词", level=messages.SUCCESS)

@admin.action(description="屏蔽（→违规）")
def block_review_selected(self, request, queryset):
    count = queryset.filter(risk_level="pending_review").update(risk_level="blocked")
    self.message_user(request, f"已屏蔽 {count} 个待审核词", level=messages.SUCCESS)
```

---

### Task 5: 前端 API 排除 pending_review

**Files:**
- Modify: `D:\aiFire\backend\apps\trends\api\views.py`

- [ ] **Step 1: 在 PhraseListView 和 PlatformSummaryView 中排除 pending_review**

`PhraseListView.get_queryset` 中，找到 `exclude(risk_level=RiskLevel.BLOCKED)` 这行，改为：

```python
qs = qs.exclude(risk_level__in=[RiskLevel.BLOCKED, RiskLevel.PENDING_REVIEW])
```

`PlatformSummaryView.get` 中，同样修改：

```python
phrases = Phrase.objects.filter(is_deleted=False, platform=platform).exclude(
    risk_level__in=[RiskLevel.BLOCKED, RiskLevel.PENDING_REVIEW]
)
```

`PhraseDetailView.queryset` 中：

```python
queryset = Phrase.objects.exclude(
    risk_level__in=[RiskLevel.BLOCKED, RiskLevel.PENDING_REVIEW]
).filter(is_deleted=False).prefetch_related(
    "metrics", "evidences", "generated_titles"
)
```

---

### Task 6: 编写测试

**Files:**
- Create: `D:\aiFire\backend\tests\trends\test_ai_legal_review.py`

- [ ] **Step 1: 写测试**

```python
from django.test import TestCase
from apps.trends.models import RiskLevel, Phrase, Platform
from apps.trends.services.risk import apply_ai_verdict


class AIRiskAssessmentTests(TestCase):
    def test_apply_safe_verdict(self):
        result = apply_ai_verdict("test", {"verdict": "SAFE", "reason": ""}, RiskLevel.LOW)
        self.assertEqual(result, RiskLevel.LOW)

    def test_apply_review_verdict(self):
        result = apply_ai_verdict("test", {"verdict": "REVIEW", "reason": "borderline"}, RiskLevel.LOW)
        self.assertEqual(result, RiskLevel.PENDING_REVIEW)

    def test_apply_block_verdict(self):
        result = apply_ai_verdict("test", {"verdict": "BLOCK", "reason": "violates policy"}, RiskLevel.LOW)
        self.assertEqual(result, RiskLevel.BLOCKED)

    def test_respects_existing_high_risk(self):
        """已有 HIGH 风险的词不被 AI 降级"""
        result = apply_ai_verdict("test", {"verdict": "SAFE", "reason": ""}, RiskLevel.HIGH)
        self.assertEqual(result, RiskLevel.HIGH)

    def test_unknown_verdict_defaults_safe(self):
        result = apply_ai_verdict("test", {"verdict": "UNKNOWN", "reason": ""}, RiskLevel.LOW)
        self.assertEqual(result, RiskLevel.LOW)


class PhraseAPIExclusionTests(TestCase):
    def setUp(self):
        self.safe = Phrase.objects.create(text="safe word", platform=Platform.TIKTOK, risk_level=RiskLevel.LOW)
        self.pending = Phrase.objects.create(text="pending word", platform=Platform.TIKTOK, risk_level=RiskLevel.PENDING_REVIEW)
        self.blocked = Phrase.objects.create(text="blocked word", platform=Platform.TIKTOK, risk_level=RiskLevel.BLOCKED)

    def test_excludes_pending_review(self):
        qs = Phrase.objects.exclude(risk_level__in=[RiskLevel.BLOCKED, RiskLevel.PENDING_REVIEW])
        ids = set(qs.values_list("id", flat=True))
        self.assertIn(self.safe.id, ids)
        self.assertNotIn(self.pending.id, ids)
        self.assertNotIn(self.blocked.id, ids)
```

- [ ] **Step 2: 运行测试**

```powershell
D:\aiFire\.venv\Scripts\python.exe -m pytest D:\aiFire\backend\tests\trends\test_ai_legal_review.py -v --tb=short
```

Expected: All 6 tests pass.

---

### Task 7: 最终验证

- [ ] **Step 1: 全部后端测试**

```powershell
D:\aiFire\.venv\Scripts\python.exe -m pytest D:\aiFire\backend\tests\ -v --tb=short 2>&1 | Select-Object -Last 30
```

- [ ] **Step 2: 前端构建**

```powershell
cd D:\aiFire\frontend; npm run build 2>&1 | Select-Object -Last 10
```

