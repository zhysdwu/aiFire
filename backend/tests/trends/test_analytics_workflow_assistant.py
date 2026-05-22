import pytest
from django.db import IntegrityError
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.trends.management.commands import ensure_daily_fetch as ensure_daily_fetch_module
from apps.trends.models import (
    AssistantMessageLog,
    DailyFetchCheckpoint,
    DailyWorkflowRun,
    Phrase,
    PhraseMetricWindow,
    Platform,
    RiskLevel,
    Window,
    WorkflowStatus,
)


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
def test_daily_workflow_run_is_unique_per_platform_and_date():
    today = timezone.localdate()
    DailyWorkflowRun.objects.create(platform=Platform.TIKTOK, run_date=today)

    with pytest.raises(IntegrityError):
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


@pytest.mark.django_db
def test_analytics_overview_returns_all_social_platforms(api_client):
    response = api_client.get("/api/analytics/overview/")

    assert response.status_code == 200
    platforms = {item["platform"] for item in response.data["platforms"]}
    assert platforms == {"tiktok", "instagram", "facebook"}
    assert "comparison" in response.data


@pytest.mark.django_db
def test_analytics_overview_ignores_deleted_and_blocked_phrases(api_client):
    from apps.trends.models import Phrase

    visible = Phrase.objects.create(text="quiet luxury", platform=Platform.TIKTOK, risk_level=RiskLevel.LOW)
    deleted = Phrase.objects.create(text="deleted trend", platform=Platform.TIKTOK, risk_level=RiskLevel.LOW, is_deleted=True)
    blocked = Phrase.objects.create(text="blocked trend", platform=Platform.TIKTOK, risk_level=RiskLevel.BLOCKED)
    PhraseMetricWindow.objects.create(phrase=visible, window=Window.H24, heat_score=80)
    PhraseMetricWindow.objects.create(phrase=deleted, window=Window.H24, heat_score=90)
    PhraseMetricWindow.objects.create(phrase=blocked, window=Window.H24, heat_score=100)

    response = api_client.get("/api/analytics/overview/")

    assert response.status_code == 200
    tiktok = next(item for item in response.data["platforms"] if item["platform"] == Platform.TIKTOK)
    assert tiktok["total_phrases"] == 1
    assert tiktok["avg_heat_score"] == 80.0


@pytest.mark.django_db
def test_workflow_status_returns_today_rows(api_client):
    response = api_client.get("/api/workflow/status/")

    assert response.status_code == 200
    assert len(response.data["runs"]) == 3
    assert {item["platform"] for item in response.data["runs"]} == {"tiktok", "instagram", "facebook"}


@pytest.mark.django_db
def test_assistant_chat_returns_fallback_without_api_key(api_client, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    response = api_client.post(
        "/api/assistant/chat/",
        {"platform": "tiktok", "question": "Compare platforms"},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["intent"] in {"platform_compare", "general"}
    assert response.data["answer"]
    assert AssistantMessageLog.objects.filter(platform=Platform.TIKTOK, question="Compare platforms").exists()


@pytest.mark.django_db
def test_assistant_chat_ignores_invalid_phrase_id(api_client, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    response = api_client.post(
        "/api/assistant/chat/",
        {"platform": "instagram", "phrase_id": "not-a-number", "question": "分析这个平台"},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["answer"]
    assert AssistantMessageLog.objects.filter(platform=Platform.INSTAGRAM, phrase__isnull=True).exists()


@pytest.mark.django_db
def test_phrase_soft_delete_rejects_non_admin_user(api_client):
    User = get_user_model()
    user = User.objects.create_user(username="normal", password="pass12345")
    api_client.force_authenticate(user=user)

    phrase = Phrase.objects.create(text="non admin trend", platform=Platform.TIKTOK, risk_level=RiskLevel.LOW)
    response = api_client.post(
        f"/api/phrases/{phrase.id}/soft-delete/",
        {"reason_type": "invalid"},
        format="json",
    )

    phrase.refresh_from_db()
    assert response.status_code in {401, 403}
    assert phrase.is_deleted is False


@pytest.mark.django_db
def test_ensure_daily_fetch_marks_skipped_workflow_runs(monkeypatch):
    for platform in [Platform.TIKTOK, Platform.INSTAGRAM, Platform.FACEBOOK]:
        checkpoint = DailyFetchCheckpoint.get_for_platform(platform)
        checkpoint.last_success_date = timezone.localdate()
        checkpoint.last_success_at = timezone.now()
        checkpoint.save(update_fields=["last_success_date", "last_success_at", "updated_at"])

    monkeypatch.setattr(ensure_daily_fetch_module, "call_command", lambda *args, **kwargs: True)

    ensure_daily_fetch_module.Command().handle(limit=60, source="official", region="US", failover_after_minutes=30)

    assert set(DailyWorkflowRun.objects.values_list("fetch_status", flat=True)) == {WorkflowStatus.SKIPPED}


@pytest.mark.django_db
def test_ensure_daily_fetch_marks_success_workflow_runs(monkeypatch):
    for platform in [Platform.TIKTOK, Platform.INSTAGRAM, Platform.FACEBOOK]:
        DailyFetchCheckpoint.get_for_platform(platform)

    monkeypatch.setattr(ensure_daily_fetch_module, "call_command", lambda *args, **kwargs: True)

    ensure_daily_fetch_module.Command().handle(limit=60, source="official", region="US", failover_after_minutes=30)

    assert set(DailyWorkflowRun.objects.values_list("fetch_status", flat=True)) == {WorkflowStatus.SUCCESS}


@pytest.mark.django_db
def test_ensure_daily_fetch_marks_failure_workflow_runs(monkeypatch):
    for platform in [Platform.TIKTOK, Platform.INSTAGRAM, Platform.FACEBOOK]:
        DailyFetchCheckpoint.get_for_platform(platform)

    monkeypatch.setattr(ensure_daily_fetch_module, "call_command", lambda *args, **kwargs: False)

    ensure_daily_fetch_module.Command().handle(limit=60, source="official", region="US", failover_after_minutes=30)

    assert set(DailyWorkflowRun.objects.values_list("fetch_status", flat=True)) == {WorkflowStatus.FAILED}
