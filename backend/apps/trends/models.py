from __future__ import annotations

from django.db import models


class Platform(models.TextChoices):
    TIKTOK = "tiktok", "TikTok"
    INSTAGRAM = "instagram", "Instagram"
    FACEBOOK = "facebook", "Facebook"
    GOOGLE_TRENDS = "gtrends", "Google Trends"
    ANSWER_THE_PUBLIC = "atp", "AnswerThePublic"


class RiskLevel(models.TextChoices):
    LOW = "low", "Low"
    MEDIUM = "medium", "Medium"
    HIGH = "high", "High"
    BLOCKED = "blocked", "Blocked"


class Window(models.TextChoices):
    H24 = "24h", "24h"
    D7 = "7d", "7d"
    D30 = "30d", "30d"


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


class DeleteReasonType(models.TextChoices):
    INVALID = "invalid", "Invalid field"
    ILLEGAL = "illegal", "Illegal field"
    DUPLICATE = "duplicate", "Duplicate field"
    CUSTOM = "custom", "Custom reason"


class Category(models.Model):
    name_zh = models.CharField(max_length=64)
    name_en = models.CharField(max_length=64)
    color_hex = models.CharField(max_length=7, default="#3B82F6")
    icon = models.CharField(max_length=64, default="tag")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.name_en} / {self.name_zh}"


class TikTokRawSnapshot(models.Model):
    platform = models.CharField(max_length=16, choices=Platform.choices, default=Platform.TIKTOK)
    region = models.CharField(max_length=8, default="US")
    source_url = models.URLField()
    external_id = models.CharField(max_length=128, db_index=True)
    title_text = models.TextField(blank=True, default="")
    caption_text = models.TextField(blank=True, default="")
    raw_metrics = models.JSONField(default=dict)
    fetched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["platform", "region", "fetched_at"])]


class Phrase(models.Model):
    text = models.CharField(max_length=255)
    platform = models.CharField(max_length=16, choices=Platform.choices, default=Platform.TIKTOK)
    language = models.CharField(max_length=8, default="en")
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL)
    risk_level = models.CharField(max_length=16, choices=RiskLevel.choices, default=RiskLevel.LOW)
    first_seen_at = models.DateTimeField(null=True, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_reason_type = models.CharField(max_length=16, choices=DeleteReasonType.choices, blank=True, default="")
    deleted_reason_text = models.TextField(blank=True, default="")
    deleted_by = models.ForeignKey("auth.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="deleted_phrases")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.text

    class Meta:
        unique_together = [("text", "platform")]


class EvidenceLink(models.Model):
    phrase = models.ForeignKey(Phrase, on_delete=models.CASCADE, related_name="evidences")
    url = models.URLField()
    title = models.CharField(max_length=255, blank=True, default="")
    fetched_at = models.DateTimeField(auto_now_add=True)


class PhraseMetricWindow(models.Model):
    phrase = models.ForeignKey(Phrase, on_delete=models.CASCADE, related_name="metrics")
    window = models.CharField(max_length=8, choices=Window.choices)
    heat_score = models.IntegerField()
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
    template = models.CharField(max_length=16, default="A")
    risk_level = models.CharField(max_length=16, choices=RiskLevel.choices, default=RiskLevel.LOW)
    is_published = models.BooleanField(default=False)
    feedback_text = models.TextField(blank=True, default="")
    ai_reply = models.TextField(blank=True, default="")
    refined_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)


class RuleConfig(models.Model):
    key = models.CharField(max_length=64, unique=True)
    value = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)


class DataSourceStatus(models.Model):
    source_key = models.CharField(max_length=64, unique=True)
    display_name = models.CharField(max_length=128)
    platform = models.CharField(max_length=16, choices=Platform.choices, default=Platform.TIKTOK)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_success = models.BooleanField(default=False)
    last_count = models.IntegerField(default=0)
    consecutive_failures = models.IntegerField(default=0)
    first_failure_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.display_name} ({self.source_key})"


class DailyFetchCheckpoint(models.Model):
    key = models.CharField(max_length=32, unique=True)
    last_success_date = models.DateField(null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def get_default(cls) -> "DailyFetchCheckpoint":
        return cls.get_for_platform(Platform.TIKTOK)

    @classmethod
    def get_for_platform(cls, platform: str) -> "DailyFetchCheckpoint":
        obj, _ = cls.objects.get_or_create(key=platform)
        return obj


class PhraseDeleteLog(models.Model):
    phrase = models.ForeignKey(Phrase, on_delete=models.CASCADE, related_name="delete_logs")
    operator = models.ForeignKey("auth.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="phrase_delete_logs")
    reason_type = models.CharField(max_length=16, choices=DeleteReasonType.choices)
    reason_text = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)


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
    phrase = models.ForeignKey(Phrase, null=True, blank=True, on_delete=models.SET_NULL, related_name="assistant_logs")
    question = models.TextField()
    answer = models.TextField()
    intent = models.CharField(max_length=32, choices=AssistantIntent.choices, default=AssistantIntent.GENERAL)
    created_by = models.ForeignKey(
        "auth.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assistant_message_logs",
    )
    created_at = models.DateTimeField(auto_now_add=True)
