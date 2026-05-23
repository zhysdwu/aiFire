import pytest
from django.utils import timezone
from django.core.management import call_command

from apps.trends.management.commands import ensure_daily_fetch as ensure_daily_fetch_module
from apps.trends.models import DailyFetchCheckpoint, DailyWorkflowRun, Platform, WorkflowStatus


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
def test_run_daily_pipeline_returns_status_string():
    result = call_command("run_daily_pipeline", "--seed-demo")

    assert result == "success"
