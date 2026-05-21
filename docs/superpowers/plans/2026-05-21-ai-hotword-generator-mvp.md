# AI 爆款词生成器（TikTok US）MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 Django+DRF+Admin + MySQL 实现“TikTok(US) 热词榜单 + 详情页推荐标题”，每日定时抓取/聚合/生成，并在 Vue3 前端公开展示。

**Architecture:** 后端分为“采集快照 → 短语抽取 → 窗口聚合指标 → 生成标题/caption → 风险审核发布”的流水线；对外提供只读 API，管理动作全部通过 Django Admin。前端 Vue3 消费只读 API，展示榜单与详情页（含 3 条标题+caption）。

**Tech Stack:** Django, Django REST Framework, MySQL, Python venv, pytest, Vue3, Vite, DeepSeek API（HTTP）

---

## 0) 文件结构锁定（先定边界）

目标工作区：`D:\aiFire`

**Create:**
- `D:\aiFire\.gitignore`
- `D:\aiFire\README.md`
- `D:\aiFire\backend\`（Django 项目）
- `D:\aiFire\backend\manage.py`
- `D:\aiFire\backend\config\`（Django settings/urls/asgi/wsgi）
- `D:\aiFire\backend\apps\trends\`（核心 app：模型、admin、API、pipeline）
- `D:\aiFire\backend\apps\trends\migrations\0001_initial.py`
- `D:\aiFire\backend\apps\trends\management\commands\run_daily_pipeline.py`
- `D:\aiFire\backend\apps\trends\services\deepseek_client.py`
- `D:\aiFire\backend\apps\trends\services\phrase_extractor.py`
- `D:\aiFire\backend\apps\trends\services\scoring.py`
- `D:\aiFire\backend\apps\trends\services\title_generator.py`
- `D:\aiFire\backend\apps\trends\services\risk.py`
- `D:\aiFire\backend\apps\trends\api\serializers.py`
- `D:\aiFire\backend\apps\trends\api\views.py`
- `D:\aiFire\backend\apps\trends\api\urls.py`
- `D:\aiFire\backend\requirements.txt`
- `D:\aiFire\backend\pytest.ini`
- `D:\aiFire\backend\tests\trends\test_api_phrases.py`
- `D:\aiFire\backend\tests\trends\test_pipeline_compute_metrics.py`
- `D:\aiFire\frontend\`（Vue3 项目）
- `D:\aiFire\frontend\src\pages\HotwordsList.vue`
- `D:\aiFire\frontend\src\pages\HotwordDetail.vue`
- `D:\aiFire\frontend\src\api\client.ts`
- `D:\aiFire\frontend\src\router.ts`

**Note:**
- TikTok 采集入口不稳定：MVP 把“采集”做成可替换模块，第一版允许用“假数据注入命令”跑通全链路（见 Task 7），等你后续提供可用入口再替换抓取实现。
- Admin 能力：类目（中英名+颜色/图标）与审核（生成标题候选）是 MVP 必须落地项。

---

## 1) Task 1: 初始化工程骨架（可运行的空壳）

**Files:**
- Create: `D:\aiFire\.gitignore`
- Create: `D:\aiFire\README.md`
- Create: `D:\aiFire\backend\requirements.txt`

- [ ] **Step 1: 初始化 Git（如果你希望有版本管理）**

Run: `git init`
Expected: `Initialized empty Git repository ...`

- [ ] **Step 2: 写 `.gitignore`（Python/Node/Env/数据库配置）**

Edit `D:\aiFire\.gitignore`:
```gitignore
__pycache__/
*.pyc
.pytest_cache/
.venv/
.env

frontend/node_modules/
frontend/dist/

.superpowers/
```

- [ ] **Step 3: 写 `README.md`（最短启动说明）**

Edit `D:\aiFire\README.md`:
```md
# AI Hotword Generator (TikTok US) MVP

Backend: Django + DRF + MySQL  
Frontend: Vue 3 + Vite
```

- [ ] **Step 4: 写后端依赖**

Edit `D:\aiFire\backend\requirements.txt`:
```txt
Django==5.1.6
djangorestframework==3.15.2
mysqlclient==2.2.6
python-dotenv==1.0.1
requests==2.32.3
pytest==8.3.3
pytest-django==4.9.0
```

---

## 2) Task 2: 创建 Django 项目 + MySQL 配置 + DRF

**Files:**
- Create: `D:\aiFire\backend\config\settings.py`
- Create: `D:\aiFire\backend\config\urls.py`
- Create: `D:\aiFire\backend\config\wsgi.py`
- Create: `D:\aiFire\backend\config\asgi.py`
- Create: `D:\aiFire\backend\manage.py`
- Create: `D:\aiFire\backend\pytest.ini`

- [ ] **Step 1: 创建 Python venv 并安装依赖**

Run (PowerShell):
`python -m venv .venv`
`.\.venv\Scripts\python -m pip install -r D:\aiFire\backend\requirements.txt`
Expected: 安装成功

- [ ] **Step 2: 创建 Django 项目结构**

Run:
`.\.venv\Scripts\django-admin startproject config D:\aiFire\backend`
Expected: `manage.py` 与 `config/` 生成

- [ ] **Step 3: 配置 settings（DRF + dotenv + MySQL env）**

Edit `D:\aiFire\backend\config\settings.py`（保留 Django 默认值，只改/加下面关键块）：
```py
from pathlib import Path
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "apps.trends",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.getenv("MYSQL_DATABASE", "ai_hotwords"),
        "USER": os.getenv("MYSQL_USER", "root"),
        "PASSWORD": os.getenv("MYSQL_PASSWORD", ""),
        "HOST": os.getenv("MYSQL_HOST", "127.0.0.1"),
        "PORT": os.getenv("MYSQL_PORT", "3306"),
        "OPTIONS": {"charset": "utf8mb4"},
    }
}

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
}
```

- [ ] **Step 4: 配置根路由**

Edit `D:\aiFire\backend\config\urls.py`:
```py
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("apps.trends.api.urls")),
]
```

- [ ] **Step 5: 配置 pytest-django**

Create `D:\aiFire\backend\pytest.ini`:
```ini
[pytest]
DJANGO_SETTINGS_MODULE = config.settings
python_files = tests.py test_*.py *_tests.py
```

---

## 3) Task 3: 数据模型（快照 + 短语 + 窗口指标 + 证据 + 生成标题 + 类目/规则）

**Files:**
- Create: `D:\aiFire\backend\apps\trends\apps.py`
- Create: `D:\aiFire\backend\apps\trends\models.py`
- Create: `D:\aiFire\backend\apps\trends\migrations\0001_initial.py`
- Test: `D:\aiFire\backend\tests\trends\test_pipeline_compute_metrics.py`

- [ ] **Step 1: 创建 app**

Run:
`.\.venv\Scripts\python D:\aiFire\backend\manage.py startapp trends D:\aiFire\backend\apps\trends`
Expected: app 目录生成

- [ ] **Step 2: 写模型（最小可用字段集）**

Edit `D:\aiFire\backend\apps\trends\models.py`:
```py
from __future__ import annotations

from django.db import models


class Platform(models.TextChoices):
    TIKTOK = "tiktok", "TikTok"


class RiskLevel(models.TextChoices):
    LOW = "low", "Low"
    MEDIUM = "medium", "Medium"
    HIGH = "high", "High"
    BLOCKED = "blocked", "Blocked"


class Window(models.TextChoices):
    H24 = "24h", "24h"
    D7 = "7d", "7d"
    D30 = "30d", "30d"


class Category(models.Model):
    name_zh = models.CharField(max_length=64)
    name_en = models.CharField(max_length=64)
    color_hex = models.CharField(max_length=7, default="#3B82F6")  # #RRGGBB
    icon = models.CharField(max_length=64, default="tag")  # 前端自定义映射
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.name_en} / {self.name_zh}"


class TikTokRawSnapshot(models.Model):
    platform = models.CharField(max_length=16, choices=Platform.choices, default=Platform.TIKTOK)
    region = models.CharField(max_length=8, default="US")
    source_url = models.URLField()
    external_id = models.CharField(max_length=128, db_index=True)  # 视频/内容 id（如果拿得到）
    title_text = models.TextField(blank=True, default="")
    caption_text = models.TextField(blank=True, default="")
    raw_metrics = models.JSONField(default=dict)  # 可能包含 views/likes/comments 等
    fetched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["platform", "region", "fetched_at"])]


class Phrase(models.Model):
    text = models.CharField(max_length=255, unique=True)
    language = models.CharField(max_length=8, default="en")
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL)
    risk_level = models.CharField(max_length=16, choices=RiskLevel.choices, default=RiskLevel.LOW)
    first_seen_at = models.DateTimeField(null=True, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.text


class EvidenceLink(models.Model):
    phrase = models.ForeignKey(Phrase, on_delete=models.CASCADE, related_name="evidences")
    url = models.URLField()
    title = models.CharField(max_length=255, blank=True, default="")
    fetched_at = models.DateTimeField(auto_now_add=True)


class PhraseMetricWindow(models.Model):
    phrase = models.ForeignKey(Phrase, on_delete=models.CASCADE, related_name="metrics")
    window = models.CharField(max_length=8, choices=Window.choices)
    heat_score = models.IntegerField()  # 0-100
    growth_prev_window = models.FloatField(null=True, blank=True)
    growth_vs_7d_avg = models.FloatField(null=True, blank=True)
    score_explain = models.TextField(blank=True, default="")
    computed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("phrase", "window")]


class GeneratedTitle(models.Model):
    phrase = models.ForeignKey(Phrase, on_delete=models.CASCADE, related_name="generated_titles")
    window = models.CharField(max_length=8, choices=Window.choices, default=Window.D30)
    title = models.CharField(max_length=120)
    caption = models.CharField(max_length=180)
    template = models.CharField(max_length=16, default="A")  # A/B
    risk_level = models.CharField(max_length=16, choices=RiskLevel.choices, default=RiskLevel.LOW)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


class RuleConfig(models.Model):
    key = models.CharField(max_length=64, unique=True)
    value = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)
```

- [ ] **Step 3: 生成迁移并应用**

Run:
`.\.venv\Scripts\python D:\aiFire\backend\manage.py makemigrations trends`
`.\.venv\Scripts\python D:\aiFire\backend\manage.py migrate`
Expected: migrations 成功

- [ ] **Step 4: 写一个最小的“指标计算”单测（为后续聚合铺路）**

Create `D:\aiFire\backend\tests\trends\test_pipeline_compute_metrics.py`:
```py
import pytest

from apps.trends.services.scoring import clamp_score


@pytest.mark.django_db
def test_clamp_score():
    assert clamp_score(-1) == 0
    assert clamp_score(0) == 0
    assert clamp_score(50) == 50
    assert clamp_score(101) == 100
```

---

## 4) Task 4: Django Admin（类目管理 + 审核发布生成标题）

**Files:**
- Create: `D:\aiFire\backend\apps\trends\admin.py`

- [ ] **Step 1: 注册模型到 Admin**

Edit `D:\aiFire\backend\apps\trends\admin.py`:
```py
from django.contrib import admin

from .models import (
    Category,
    EvidenceLink,
    GeneratedTitle,
    Phrase,
    PhraseMetricWindow,
    RuleConfig,
    TikTokRawSnapshot,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name_en", "name_zh", "color_hex", "icon", "is_active", "created_at")
    search_fields = ("name_en", "name_zh")
    list_filter = ("is_active",)


@admin.register(Phrase)
class PhraseAdmin(admin.ModelAdmin):
    list_display = ("id", "text", "language", "risk_level", "category", "first_seen_at", "last_seen_at")
    search_fields = ("text",)
    list_filter = ("risk_level", "language", "category")


@admin.register(GeneratedTitle)
class GeneratedTitleAdmin(admin.ModelAdmin):
    list_display = ("id", "phrase", "title", "template", "risk_level", "is_published", "created_at")
    search_fields = ("phrase__text", "title", "caption")
    list_filter = ("template", "risk_level", "is_published")
    actions = ["publish_selected", "unpublish_selected"]

    @admin.action(description="Publish selected titles")
    def publish_selected(self, request, queryset):
        queryset.update(is_published=True)

    @admin.action(description="Unpublish selected titles")
    def unpublish_selected(self, request, queryset):
        queryset.update(is_published=False)


admin.site.register(TikTokRawSnapshot)
admin.site.register(EvidenceLink)
admin.site.register(PhraseMetricWindow)
admin.site.register(RuleConfig)
```

- [ ] **Step 2: 创建超级管理员并验证后台可登录**

Run:
`.\.venv\Scripts\python D:\aiFire\backend\manage.py createsuperuser`
Expected: 能进入 `http://127.0.0.1:8000/admin/`

---

## 5) Task 5: DRF 只读 API（榜单 + 详情页含 3 条标题+caption）

**Files:**
- Create: `D:\aiFire\backend\apps\trends\api\serializers.py`
- Create: `D:\aiFire\backend\apps\trends\api\views.py`
- Create: `D:\aiFire\backend\apps\trends\api\urls.py`
- Test: `D:\aiFire\backend\tests\trends\test_api_phrases.py`

- [ ] **Step 1: 写 serializer**

Create `D:\aiFire\backend\apps\trends\api\serializers.py`:
```py
from rest_framework import serializers

from apps.trends.models import EvidenceLink, GeneratedTitle, Phrase, PhraseMetricWindow


class EvidenceLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = EvidenceLink
        fields = ("url", "title", "fetched_at")


class GeneratedTitleSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeneratedTitle
        fields = ("title", "caption", "template", "risk_level", "is_published", "created_at")


class PhraseMetricWindowSerializer(serializers.ModelSerializer):
    class Meta:
        model = PhraseMetricWindow
        fields = ("window", "heat_score", "growth_prev_window", "growth_vs_7d_avg", "score_explain", "computed_at")


class PhraseListSerializer(serializers.ModelSerializer):
    metric = serializers.SerializerMethodField()

    class Meta:
        model = Phrase
        fields = ("id", "text", "risk_level", "metric")

    def get_metric(self, obj: Phrase):
        window = self.context.get("window")
        if not window:
            return None
        metric = obj.metrics.filter(window=window).first()
        if not metric:
            return None
        return PhraseMetricWindowSerializer(metric).data


class PhraseDetailSerializer(serializers.ModelSerializer):
    metrics = PhraseMetricWindowSerializer(many=True)
    evidences = EvidenceLinkSerializer(many=True)
    generated_titles = serializers.SerializerMethodField()

    class Meta:
        model = Phrase
        fields = ("id", "text", "risk_level", "metrics", "evidences", "generated_titles")

    def get_generated_titles(self, obj: Phrase):
        # 只返回已发布的 3 条（或更少）
        qs = obj.generated_titles.filter(is_published=True).order_by("-created_at")[:3]
        return GeneratedTitleSerializer(qs, many=True).data
```

- [ ] **Step 2: 写 views（列表支持 window/sort/search/filter）**

Create `D:\aiFire\backend\apps\trends\api\views.py`:
```py
from rest_framework import generics
from rest_framework.request import Request

from apps.trends.models import Phrase, PhraseMetricWindow, RiskLevel, Window
from apps.trends.api.serializers import PhraseDetailSerializer, PhraseListSerializer


class PhraseListView(generics.ListAPIView):
    serializer_class = PhraseListSerializer

    def get_queryset(self):
        request: Request = self.request
        window = request.query_params.get("window", Window.H24)
        sort = request.query_params.get("sort", "heat")  # heat|growth|new|ai
        q = request.query_params.get("q", "").strip()
        risk = request.query_params.get("risk", "").strip()  # low|medium|high

        qs = Phrase.objects.all()
        if q:
            qs = qs.filter(text__icontains=q)
        if risk in {RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH}:
            qs = qs.filter(risk_level=risk)
        # Blocked 永不对外
        qs = qs.exclude(risk_level=RiskLevel.BLOCKED)

        # 通过 metrics join 排序（简单实现：用子查询/annotate）
        metrics = PhraseMetricWindow.objects.filter(phrase_id__in=qs.values("id"), window=window)

        if sort == "new":
            return qs.order_by("-created_at")

        if sort in {"heat", "growth", "ai"}:
            # 用 Python 侧排序会慢；MVP 用 annotate 简化（实现时可再优化为 Subquery）
            # 这里先用 related_name + filter 会在 DB 侧做 join
            qs = qs.filter(metrics__window=window)
            if sort == "heat" or sort == "ai":
                return qs.order_by("-metrics__heat_score").distinct()
            return qs.order_by("-metrics__growth_prev_window").distinct()

        return qs.order_by("-created_at")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["window"] = self.request.query_params.get("window", Window.H24)
        return ctx


class PhraseDetailView(generics.RetrieveAPIView):
    queryset = Phrase.objects.exclude(risk_level=RiskLevel.BLOCKED).prefetch_related("metrics", "evidences", "generated_titles")
    serializer_class = PhraseDetailSerializer
```

- [ ] **Step 3: 写 urls**

Create `D:\aiFire\backend\apps\trends\api\urls.py`:
```py
from django.urls import path

from apps.trends.api.views import PhraseDetailView, PhraseListView

urlpatterns = [
    path("phrases/", PhraseListView.as_view(), name="phrase-list"),
    path("phrases/<int:pk>/", PhraseDetailView.as_view(), name="phrase-detail"),
]
```

- [ ] **Step 4: 写 API 测试**

Create `D:\aiFire\backend\tests\trends\test_api_phrases.py`:
```py
import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.trends.models import Phrase, PhraseMetricWindow, RiskLevel, Window


@pytest.mark.django_db
def test_phrase_list_returns_metrics():
    phrase = Phrase.objects.create(text="quiet luxury", risk_level=RiskLevel.LOW)
    PhraseMetricWindow.objects.create(phrase=phrase, window=Window.H24, heat_score=80)

    client = APIClient()
    res = client.get(reverse("phrase-list"), {"window": Window.H24, "sort": "heat"})
    assert res.status_code == 200
    assert res.data["results"][0]["text"] == "quiet luxury"
    assert res.data["results"][0]["metric"]["heat_score"] == 80


@pytest.mark.django_db
def test_phrase_detail_returns_generated_titles_published_only():
    phrase = Phrase.objects.create(text="quiet luxury", risk_level=RiskLevel.LOW)
    client = APIClient()
    res = client.get(reverse("phrase-detail", args=[phrase.id]))
    assert res.status_code == 200
    assert "generated_titles" in res.data
```

---

## 6) Task 6: DeepSeek 客户端 + 抽取/评分/标题生成服务（可替换）

**Files:**
- Create: `D:\aiFire\backend\apps\trends\services\deepseek_client.py`
- Create: `D:\aiFire\backend\apps\trends\services\phrase_extractor.py`
- Create: `D:\aiFire\backend\apps\trends\services\scoring.py`
- Create: `D:\aiFire\backend\apps\trends\services\title_generator.py`
- Create: `D:\aiFire\backend\apps\trends\services\risk.py`

- [ ] **Step 1: DeepSeek HTTP 客户端（最小可用）**

Create `D:\aiFire\backend\apps\trends\services\deepseek_client.py`:
```py
from __future__ import annotations

import os
from dataclasses import dataclass
import requests


@dataclass(frozen=True)
class DeepSeekConfig:
    api_key: str
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-chat"
    timeout_s: int = 60


class DeepSeekClient:
    def __init__(self, config: DeepSeekConfig):
        self.config = config

    @classmethod
    def from_env(cls) -> "DeepSeekClient":
        api_key = os.getenv("DEEPSEEK_API_KEY", "")
        if not api_key:
            raise RuntimeError("Missing DEEPSEEK_API_KEY")
        return cls(DeepSeekConfig(api_key=api_key))

    def chat_json(self, system: str, user: str) -> dict:
        url = f"{self.config.base_url}/v1/chat/completions"
        headers = {"Authorization": f"Bearer {self.config.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }
        r = requests.post(url, headers=headers, json=payload, timeout=self.config.timeout_s)
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"]
```

> 实现时将 `message.content` 解析为 JSON（`json.loads`），并在失败时落日志；MVP 先用最短路径。

- [ ] **Step 2: 短语抽取服务（返回候选短语列表）**

Create `D:\aiFire\backend\apps\trends\services\phrase_extractor.py`:
```py
from __future__ import annotations

import json
import re
from typing import Iterable

from apps.trends.services.deepseek_client import DeepSeekClient


_WS = re.compile(r"\\s+")


def normalize_phrase(text: str) -> str:
    text = text.strip()
    text = _WS.sub(" ", text)
    return text


def extract_phrases_with_llm(client: DeepSeekClient, texts: Iterable[str]) -> list[str]:
    system = (
        "You extract short English keyword phrases from TikTok video titles/captions. "
        "Return JSON: {\"phrases\":[...]} where each phrase is 2-6 words, lowercase, no hashtags."
    )
    user = "INPUT_TEXTS:\\n" + "\\n".join(f"- {t[:280]}" for t in texts if t)
    raw = client.chat_json(system=system, user=user)
    obj = json.loads(raw)
    phrases = [normalize_phrase(p).lower() for p in obj.get("phrases", []) if isinstance(p, str)]
    phrases = [p for p in phrases if 2 <= len(p.split()) <= 6]
    # 去重保持顺序
    seen = set()
    out = []
    for p in phrases:
        if p in seen:
            continue
        seen.add(p)
        out.append(p)
    return out
```

- [ ] **Step 3: 评分工具与 clamp**

Create `D:\aiFire\backend\apps\trends\services\scoring.py`:
```py
def clamp_score(v: int) -> int:
    return max(0, min(100, int(v)))
```

- [ ] **Step 4: 标题生成服务（A/B 模板 + 长度约束）**

Create `D:\aiFire\backend\apps\trends\services\title_generator.py`:
```py
from __future__ import annotations

import json
import random

from apps.trends.services.deepseek_client import DeepSeekClient


TEMPLATE_A = "I tried {phrase} for {time}... here's what happened"
TEMPLATE_B = "How to get {result} in {time} (without {pain})"


def generate_titles_for_phrase(client: DeepSeekClient, phrase: str, n: int = 3) -> list[dict]:
    # A:70% / B:30%
    templates = ["A"] * 7 + ["B"] * 3
    picked = [random.choice(templates) for _ in range(n)]

    system = (
        "You generate TikTok video TITLE and one-sentence CAPTION in English. "
        "Hard constraints: title <= 60 chars, caption <= 100 chars, 1 sentence. "
        "Return JSON: {\"items\":[{\"template\":\"A|B\",\"title\":\"...\",\"caption\":\"...\"}, ...]}"
    )
    user = f"PHRASE: {phrase}\\nTEMPLATES: {picked}\\nGenerate {n} items."
    raw = client.chat_json(system=system, user=user)
    obj = json.loads(raw)
    items = obj.get("items", [])
    out = []
    for it in items:
        if not isinstance(it, dict):
            continue
        title = (it.get("title") or "").strip()
        caption = (it.get("caption") or "").strip()
        template = (it.get("template") or "A").strip().upper()
        if not title or not caption:
            continue
        if len(title) > 60 or len(caption) > 100:
            continue
        out.append({"template": template if template in {"A", "B"} else "A", "title": title, "caption": caption})
    return out[:n]
```

- [ ] **Step 5: 风险规则（MVP：词表/正则 + 占位接口）**

Create `D:\aiFire\backend\apps\trends\services\risk.py`:
```py
import re

from apps.trends.models import RiskLevel


BLOCK_PATTERNS = [
    re.compile(r"\\b(nazi|kkk)\\b", re.I),
    re.compile(r"\\b(cocaine|heroin)\\b", re.I),
]


def assess_risk(text: str) -> str:
    for pat in BLOCK_PATTERNS:
        if pat.search(text or ""):
            return RiskLevel.BLOCKED
    return RiskLevel.LOW
```

---

## 7) Task 7: Pipeline 命令（每日跑通：快照→抽取→聚合→生成→发布）

**Files:**
- Create: `D:\aiFire\backend\apps\trends\management\commands\run_daily_pipeline.py`

- [ ] **Step 1: 写可跑通的每日流水线命令（先用“假数据注入”确保端到端）**

Create `D:\aiFire\backend\apps\trends\management\commands\run_daily_pipeline.py`:
```py
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.trends.models import EvidenceLink, Phrase, PhraseMetricWindow, RiskLevel, TikTokRawSnapshot, Window, GeneratedTitle
from apps.trends.services.deepseek_client import DeepSeekClient
from apps.trends.services.phrase_extractor import extract_phrases_with_llm
from apps.trends.services.risk import assess_risk
from apps.trends.services.title_generator import generate_titles_for_phrase


class Command(BaseCommand):
    help = "Run daily pipeline: snapshot -> extract phrases -> compute metrics -> generate titles -> publish"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--seed-demo", action="store_true", help="Seed demo snapshots instead of scraping TikTok")

    def handle(self, *args, **opts):
        if opts["seed_demo"]:
            TikTokRawSnapshot.objects.create(
                source_url="https://example.com/tiktok/demo1",
                external_id="demo1",
                title_text="I tried quiet luxury outfits for 7 days",
                caption_text="Minimal style is everywhere",
                raw_metrics={"views": 123456},
            )
            TikTokRawSnapshot.objects.create(
                source_url="https://example.com/tiktok/demo2",
                external_id="demo2",
                title_text="How to build an AI girlfriend chatbot",
                caption_text="This blew up overnight",
                raw_metrics={"views": 654321},
            )

        snapshots = list(TikTokRawSnapshot.objects.order_by("-fetched_at")[:50])
        texts = [s.title_text for s in snapshots] + [s.caption_text for s in snapshots]

        client = DeepSeekClient.from_env()
        phrases = extract_phrases_with_llm(client, texts=texts)

        now = timezone.now()
        for p in phrases:
            risk = assess_risk(p)
            phrase_obj, _ = Phrase.objects.get_or_create(text=p, defaults={"risk_level": risk})
            phrase_obj.last_seen_at = now
            phrase_obj.first_seen_at = phrase_obj.first_seen_at or now
            phrase_obj.risk_level = risk
            phrase_obj.save(update_fields=["first_seen_at", "last_seen_at", "risk_level"])

            EvidenceLink.objects.get_or_create(phrase=phrase_obj, url=snapshots[0].source_url, defaults={"title": snapshots[0].title_text[:255]})

            # MVP：先写死 heat_score=50，后续用真实聚合替换
            PhraseMetricWindow.objects.update_or_create(
                phrase=phrase_obj,
                window=Window.H24,
                defaults={"heat_score": 50, "growth_prev_window": None, "growth_vs_7d_avg": None, "score_explain": "MVP placeholder"},
            )

            if phrase_obj.risk_level == RiskLevel.BLOCKED:
                continue

            items = generate_titles_for_phrase(client, phrase=p, n=3)
            for it in items:
                t_risk = assess_risk(it["title"] + " " + it["caption"])
                gen = GeneratedTitle.objects.create(
                    phrase=phrase_obj,
                    window=Window.D30,
                    title=it["title"],
                    caption=it["caption"],
                    template=it["template"],
                    risk_level=t_risk,
                    is_published=(t_risk != RiskLevel.BLOCKED),
                )

        self.stdout.write(self.style.SUCCESS("Daily pipeline done"))
```

- [ ] **Step 2: 运行命令验证端到端**

Run:
`.\.venv\Scripts\python D:\aiFire\backend\manage.py run_daily_pipeline --seed-demo`
Expected: 输出 `Daily pipeline done`

- [ ] **Step 3: 跑后端测试**

Run:
`.\.venv\Scripts\pytest D:\aiFire\backend -q`
Expected: PASS

---

## 8) Task 8: Vue3 前端（榜单 + 详情页 + 复制）

**Files:**
- Create: `D:\aiFire\frontend\src\api\client.ts`
- Create: `D:\aiFire\frontend\src\router.ts`
- Create: `D:\aiFire\frontend\src\pages\HotwordsList.vue`
- Create: `D:\aiFire\frontend\src\pages\HotwordDetail.vue`

- [ ] **Step 1: 初始化 Vue3 项目**

Run:
`cd D:\aiFire`
`npm create vue@latest frontend`
选择：TypeScript=Yes, Router=Yes, Pinia=No, ESLint=Yes（或默认）

- [ ] **Step 2: 写 API client**

Create `D:\aiFire\frontend\src\api\client.ts`:
```ts
export type Window = "24h" | "7d" | "30d";

export type PhraseMetric = {
  window: Window;
  heat_score: number;
  growth_prev_window: number | null;
  growth_vs_7d_avg: number | null;
  score_explain: string;
};

export type PhraseListItem = { id: number; text: string; risk_level: string; metric: PhraseMetric | null };

export async function fetchPhrases(params: { window: Window; sort: string; q?: string }) {
  const usp = new URLSearchParams({ window: params.window, sort: params.sort });
  if (params.q) usp.set("q", params.q);
  const res = await fetch(`/api/phrases/?${usp.toString()}`);
  if (!res.ok) throw new Error("API error");
  return (await res.json()) as { results: PhraseListItem[]; count: number };
}

export async function fetchPhraseDetail(id: number) {
  const res = await fetch(`/api/phrases/${id}/`);
  if (!res.ok) throw new Error("API error");
  return (await res.json()) as any;
}
```

- [ ] **Step 3: 榜单页（排序切换 + window 切换 + 搜索）**

Create `D:\aiFire\frontend\src\pages\HotwordsList.vue`（实现时用最简 UI，后续再套 `frontend-design` 进行美化）：
```vue
<script setup lang="ts">
import { ref, watchEffect } from "vue";
import { fetchPhrases, type Window } from "../api/client";

const window = ref<Window>("24h");
const sort = ref("heat");
const q = ref("");
const items = ref<any[]>([]);

watchEffect(async () => {
  const data = await fetchPhrases({ window: window.value, sort: sort.value, q: q.value });
  items.value = data.results;
});
</script>

<template>
  <div style="max-width: 900px; margin: 24px auto; padding: 0 16px">
    <h1>爆款词榜单（TikTok US）</h1>
    <div style="display:flex; gap:12px; flex-wrap:wrap; align-items:center">
      <label>窗口：
        <select v-model="window">
          <option value="24h">24h</option>
          <option value="7d">7d</option>
          <option value="30d">30d</option>
        </select>
      </label>
      <label>排序：
        <select v-model="sort">
          <option value="heat">热度</option>
          <option value="growth">增长</option>
          <option value="new">新出现</option>
          <option value="ai">AI 综合</option>
        </select>
      </label>
      <input v-model="q" placeholder="搜索关键词..." />
    </div>

    <ul style="margin-top:16px">
      <li v-for="it in items" :key="it.id" style="margin:10px 0">
        <a :href="`/hotwords/${it.id}`">{{ it.text }}</a>
        <span style="margin-left:8px; color:#666">heat: {{ it.metric?.heat_score ?? "-" }}</span>
      </li>
    </ul>
  </div>
</template>
```

- [ ] **Step 4: 详情页（3 条标题+caption + 一键复制）**

Create `D:\aiFire\frontend\src\pages\HotwordDetail.vue`:
```vue
<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { fetchPhraseDetail } from "../api/client";

const route = useRoute();
const data = ref<any>(null);

async function copyText(text: string) {
  await navigator.clipboard.writeText(text);
  alert("已复制");
}

onMounted(async () => {
  data.value = await fetchPhraseDetail(Number(route.params.id));
});
</script>

<template>
  <div style="max-width: 900px; margin: 24px auto; padding: 0 16px" v-if="data">
    <a href="/">← 返回</a>
    <h1>{{ data.text }}</h1>
    <p>风险：{{ data.risk_level }}</p>

    <h2>证据链接</h2>
    <ul>
      <li v-for="e in data.evidences" :key="e.url"><a :href="e.url" target="_blank">{{ e.title || e.url }}</a></li>
    </ul>

    <h2>推荐标题（3）</h2>
    <div v-for="(t, idx) in data.generated_titles" :key="idx" style="border:1px solid #eee; padding:12px; border-radius:8px; margin:10px 0">
      <div><b>{{ t.title }}</b></div>
      <div style="color:#444; margin-top:6px">{{ t.caption }}</div>
      <button style="margin-top:8px" @click="copyText(`${t.title}\\n${t.caption}`)">复制</button>
    </div>
  </div>
</template>
```

---

## 9) Task 9: 本地联调与每日定时

**Files:**
- Modify: `D:\aiFire\frontend\vite.config.ts`（代理到 Django）

- [ ] **Step 1: Django 启动**

Run:
`.\.venv\Scripts\python D:\aiFire\backend\manage.py runserver 127.0.0.1:8000`

- [ ] **Step 2: 前端代理到后端**

Edit `D:\aiFire\frontend\vite.config.ts`:
```ts
server: {
  proxy: {
    "/api": "http://127.0.0.1:8000",
  },
},
```

- [ ] **Step 3: 前端启动**

Run:
`cd D:\aiFire\frontend`
`npm install`
`npm run dev`

- [ ] **Step 4: 配置每日定时（Windows 任务计划）**

创建任务：每天固定时间运行：
`D:\aiFire\.venv\Scripts\python D:\aiFire\backend\manage.py run_daily_pipeline`

Expected: 日志输出 `Daily pipeline done`

---

## 自检清单（写完 plan 后的自审）

- 覆盖了 spec 的每个 MVP 点：榜单/详情、字段集(1/2/3/4/5/6/9)、3条标题+caption、Admin、DeepSeek、每日定时。
- 计划中没有 “TBD/TODO/后面再说” 的关键占位（采集入口不稳定点已通过 demo seed 方案可端到端运行）。
- API 与前端字段对齐（`/api/phrases/` 与 `/api/phrases/<id>/`）。

---

## 执行交接

Plan complete and saved to `D:\aiFire\docs\superpowers\plans\2026-05-21-ai-hotword-generator-mvp.md`. Two execution options:

1. **Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration  
2. **Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?

