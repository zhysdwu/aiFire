import pytest
from django.utils import timezone
from django.core.management import call_command

from apps.trends.management.commands import ensure_daily_fetch as ensure_daily_fetch_module
from apps.trends.management.commands import run_daily_pipeline as pipeline_module
from apps.trends.models import DailyFetchCheckpoint, DailyWorkflowRun, Phrase, Platform, RiskLevel, WorkflowStatus


ALL_SOCIAL = [Platform.TIKTOK, Platform.INSTAGRAM, Platform.FACEBOOK, Platform.YOUTUBE]


@pytest.mark.django_db
def test_skip_when_today_already_success(monkeypatch):
    for platform in ALL_SOCIAL:
        checkpoint = DailyFetchCheckpoint.get_for_platform(platform)
        checkpoint.last_success_date = timezone.localdate()
        checkpoint.last_success_at = timezone.now()
        checkpoint.save(update_fields=["last_success_date", "last_success_at", "updated_at"])

    called = {"value": False}

    def fake_call_command(*args, **kwargs):
        called["value"] = True
        return True

    monkeypatch.setattr(ensure_daily_fetch_module, "call_command", fake_call_command)

    command = ensure_daily_fetch_module.Command()
    command.handle(limit=60, source="official", region="US", failover_after_minutes=30)

    assert called["value"] is False


@pytest.mark.django_db
def test_update_checkpoint_when_pipeline_success(monkeypatch):
    for platform in ALL_SOCIAL:
        checkpoint = DailyFetchCheckpoint.get_for_platform(platform)
        checkpoint.last_success_date = None
        checkpoint.last_success_at = None
        checkpoint.save(update_fields=["last_success_date", "last_success_at", "updated_at"])

    calls = []

    def fake_call_command(*args, **kwargs):
        calls.append((args, kwargs))
        for platform in ALL_SOCIAL:
            DailyWorkflowRun.objects.update_or_create(
                platform=platform,
                run_date=timezone.localdate(),
                defaults={"fetch_status": WorkflowStatus.SUCCESS},
            )
        return True

    monkeypatch.setattr(ensure_daily_fetch_module, "call_command", fake_call_command)

    command = ensure_daily_fetch_module.Command()
    command.handle(limit=60, source="official", region="US", failover_after_minutes=30)

    assert len(calls) == 1
    for platform in ALL_SOCIAL:
        checkpoint = DailyFetchCheckpoint.get_for_platform(platform)
        checkpoint.refresh_from_db()
        assert checkpoint.last_success_date == timezone.localdate()
        assert checkpoint.last_success_at is not None
        workflow = DailyWorkflowRun.objects.get(platform=platform, run_date=timezone.localdate())
        assert workflow.fetch_status == WorkflowStatus.SUCCESS


@pytest.mark.django_db
def test_keep_checkpoint_when_pipeline_failed(monkeypatch):
    for platform in ALL_SOCIAL:
        checkpoint = DailyFetchCheckpoint.get_for_platform(platform)
        checkpoint.last_success_date = None
        checkpoint.last_success_at = None
        checkpoint.save(update_fields=["last_success_date", "last_success_at", "updated_at"])

    def fake_call_command(*args, **kwargs):
        return False

    monkeypatch.setattr(ensure_daily_fetch_module, "call_command", fake_call_command)

    command = ensure_daily_fetch_module.Command()
    command.handle(limit=60, source="official", region="US", failover_after_minutes=30)

    for platform in ALL_SOCIAL:
        checkpoint = DailyFetchCheckpoint.get_for_platform(platform)
        checkpoint.refresh_from_db()
        assert checkpoint.last_success_date is None
        assert checkpoint.last_success_at is None


@pytest.mark.django_db
def test_skip_auto_fetch_when_today_failed_recently(monkeypatch):
    today = timezone.localdate()
    failed_run = DailyWorkflowRun.objects.create(
        platform=Platform.TIKTOK,
        run_date=today,
        fetch_status=WorkflowStatus.FAILED,
        last_message="network failed",
    )
    calls = []

    def fake_call_command(*args, **kwargs):
        calls.append((args, kwargs))
        return True

    monkeypatch.setattr(ensure_daily_fetch_module, "call_command", fake_call_command)

    result = ensure_daily_fetch_module.Command().handle(
        limit=60,
        source="official",
        region="US",
        failover_after_minutes=30,
        failure_retry_after_minutes=60,
    )

    assert result == "skipped"
    assert calls == []
    failed_run.refresh_from_db()
    assert failed_run.fetch_status == WorkflowStatus.FAILED


@pytest.mark.django_db
def test_retry_auto_fetch_when_today_failure_is_older_than_one_hour(monkeypatch):
    today = timezone.localdate()
    old_failure_at = timezone.now() - timezone.timedelta(minutes=61)
    DailyWorkflowRun.objects.create(
        platform=Platform.TIKTOK,
        run_date=today,
        fetch_status=WorkflowStatus.FAILED,
        last_message="network failed",
    )
    DailyWorkflowRun.objects.filter(platform=Platform.TIKTOK, run_date=today).update(
        updated_at=old_failure_at,
        finished_at=old_failure_at,
    )
    calls = []

    def fake_call_command(*args, **kwargs):
        calls.append((args, kwargs))
        return False

    monkeypatch.setattr(ensure_daily_fetch_module, "call_command", fake_call_command)

    result = ensure_daily_fetch_module.Command().handle(
        limit=60,
        source="official",
        region="US",
        failover_after_minutes=30,
        failure_retry_after_minutes=60,
    )

    assert result == "failed"
    assert len(calls) == 1


@pytest.mark.django_db
def test_daily_checkpoint_is_platform_scoped():
    tiktok = DailyFetchCheckpoint.get_for_platform(Platform.TIKTOK)
    instagram = DailyFetchCheckpoint.get_for_platform(Platform.INSTAGRAM)
    facebook = DailyFetchCheckpoint.get_for_platform(Platform.FACEBOOK)
    youtube = DailyFetchCheckpoint.get_for_platform(Platform.YOUTUBE)
    assert tiktok.key == Platform.TIKTOK
    assert instagram.key == Platform.INSTAGRAM
    assert facebook.key == Platform.FACEBOOK
    assert youtube.key == Platform.YOUTUBE


@pytest.mark.django_db
def test_ensure_daily_fetch_runs_once_when_any_platform_missing(monkeypatch):
    today = timezone.localdate()
    tiktok = DailyFetchCheckpoint.get_for_platform(Platform.TIKTOK)
    tiktok.last_success_date = today
    tiktok.last_success_at = timezone.now()
    tiktok.save(update_fields=["last_success_date", "last_success_at", "updated_at"])

    for platform in [Platform.INSTAGRAM, Platform.FACEBOOK, Platform.YOUTUBE]:
        cp = DailyFetchCheckpoint.get_for_platform(platform)
        cp.last_success_date = None
        cp.last_success_at = None
        cp.save(update_fields=["last_success_date", "last_success_at", "updated_at"])

    calls = []

    def fake_call_command(*args, **kwargs):
        calls.append((args, kwargs))
        for platform in [Platform.INSTAGRAM, Platform.FACEBOOK, Platform.YOUTUBE]:
            DailyWorkflowRun.objects.update_or_create(
                platform=platform,
                run_date=today,
                defaults={"fetch_status": WorkflowStatus.SUCCESS},
            )
        return True

    monkeypatch.setattr(ensure_daily_fetch_module, "call_command", fake_call_command)

    command = ensure_daily_fetch_module.Command()
    command.handle(limit=60, source="official", region="US", failover_after_minutes=30)

    assert len(calls) == 1
    for platform in [Platform.INSTAGRAM, Platform.FACEBOOK, Platform.YOUTUBE]:
        checkpoint = DailyFetchCheckpoint.get_for_platform(platform)
        checkpoint.refresh_from_db()
        assert checkpoint.last_success_date == today
        assert checkpoint.last_success_at is not None
        workflow = DailyWorkflowRun.objects.get(platform=platform, run_date=today)
        assert workflow.fetch_status == WorkflowStatus.SUCCESS


@pytest.mark.django_db
def test_run_daily_pipeline_returns_status_string(monkeypatch):
    monkeypatch.setattr(
        pipeline_module.DeepSeekClient,
        "from_env",
        classmethod(lambda cls: (_ for _ in ()).throw(RuntimeError("skip ai"))),
    )
    monkeypatch.setattr(
        pipeline_module,
        "generate_titles_basic",
        lambda phrase, n=3: [{"template": "A", "title": f"{phrase} title", "caption": "caption"}],
    )

    result = call_command("run_daily_pipeline", "--seed-demo")

    assert result == "success"


@pytest.mark.django_db
def test_run_daily_pipeline_handles_same_phrase_text_across_platforms(monkeypatch):
    for platform in ALL_SOCIAL:
        Phrase.objects.create(text="quiet luxury", platform=platform, risk_level=RiskLevel.LOW)

    def fake_collect(self, limit, region, failover_after_minutes):
        return [
            {
                "platform": Platform.TIKTOK,
                "region": region,
                "external_id": "test-quiet-luxury",
                "source_url": "https://example.com/quiet-luxury",
                "title_text": "quiet luxury",
                "caption_text": "quiet luxury",
                "raw_metrics": {
                    "views": 100000,
                    "diggCount": 10000,
                    "commentCount": 1000,
                    "shareCount": 500,
                },
            }
        ]

    monkeypatch.setattr(pipeline_module.Command, "_collect_with_failover", fake_collect)
    monkeypatch.setattr(pipeline_module, "extract_phrases_basic", lambda texts, top_k=200: ["quiet luxury"])
    monkeypatch.setattr(pipeline_module, "extract_phrases_with_llm", lambda client, texts: [])
    monkeypatch.setattr(
        pipeline_module.DeepSeekClient,
        "from_env",
        classmethod(lambda cls: (_ for _ in ()).throw(RuntimeError("skip ai"))),
    )
    monkeypatch.setattr(
        pipeline_module,
        "generate_titles_basic",
        lambda phrase, n=3: [{"template": "A", "title": f"{phrase} title", "caption": "caption"}],
    )

    result = call_command("run_daily_pipeline", "--source", "official", "--limit", "20")

    assert result == "success"
