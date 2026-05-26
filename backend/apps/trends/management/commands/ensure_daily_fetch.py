from __future__ import annotations

from datetime import timedelta

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connection
from django.db.utils import OperationalError, ProgrammingError
from django.utils import timezone

from apps.trends.models import DailyFetchCheckpoint, DailyWorkflowRun, WorkflowStatus
from apps.trends.services.analytics import SOCIAL_PLATFORMS
from apps.trends.services.workflow import mark_step


class Command(BaseCommand):
    help = "Ensure only one successful fetch per day based on per-platform checkpoints."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=60)
        parser.add_argument("--source", type=str, default="official", choices=["official", "all", "legacy"])
        parser.add_argument("--region", type=str, default="US")
        parser.add_argument("--failover-after-minutes", type=int, default=30)
        parser.add_argument("--failure-retry-after-minutes", type=int, default=60)

    @staticmethod
    def _checkpoint_table_exists() -> bool:
        table_name = DailyFetchCheckpoint._meta.db_table
        return table_name in connection.introspection.table_names()

    def _checkpoints(self):
        return {platform: DailyFetchCheckpoint.get_for_platform(platform) for platform in SOCIAL_PLATFORMS}

    def _mark_fetch_for_all(self, status: str, message: str = "") -> None:
        for platform in SOCIAL_PLATFORMS:
            mark_step(platform, "fetch", status, message)

    def _recent_failed_run(self, today, retry_after_minutes: int) -> DailyWorkflowRun | None:
        cutoff = timezone.now() - timedelta(minutes=max(1, retry_after_minutes))
        return (
            DailyWorkflowRun.objects.filter(
                run_date=today,
                fetch_status=WorkflowStatus.FAILED,
                updated_at__gte=cutoff,
            )
            .order_by("-updated_at")
            .first()
        )

    def handle(self, *args, **options):
        today = timezone.localdate()
        try:
            if not self._checkpoint_table_exists():
                self.stdout.write(self.style.WARNING("鏈娴嬪埌姣忔棩妫€鏌ョ偣琛紝璇峰厛鎵ц鏁版嵁搴撹縼绉伙細python manage.py migrate"))
                return False
            checkpoints = self._checkpoints()
        except (ProgrammingError, OperationalError):
            self.stdout.write(self.style.WARNING("鏁版嵁搴撶粨鏋勫皻鏈洿鏂帮紝璇峰厛鎵ц鏁版嵁搴撹縼绉伙細python manage.py migrate"))
            return False

        all_done = all(checkpoint.last_success_date == today for checkpoint in checkpoints.values())
        if all_done:
            self._mark_fetch_for_all(WorkflowStatus.SKIPPED, "今日已抓取成功，跳过。")
            self.stdout.write(self.style.SUCCESS(f"今日已抓取成功，跳过。日期：{today}"))
            return "skipped"

        retry_after_minutes = int(options.get("failure_retry_after_minutes") or 60)
        recent_failed_run = self._recent_failed_run(today, retry_after_minutes)
        if recent_failed_run:
            retry_at = timezone.localtime(recent_failed_run.updated_at + timedelta(minutes=max(1, retry_after_minutes)))
            self.stdout.write(
                self.style.WARNING(
                    "今日抓取失败过，自动抓取冷却中，跳过本次启动检查。"
                    f"管理员可手动重新抓取，或等待 {retry_at.strftime('%H:%M:%S')} 后自动重试。"
                )
            )
            return "skipped"

        for platform, checkpoint in checkpoints.items():
            if checkpoint.last_success_date == today:
                mark_step(platform, "fetch", WorkflowStatus.SKIPPED, "今日已抓取成功，跳过。")
            else:
                mark_step(platform, "fetch", WorkflowStatus.RUNNING, "今日尚未抓取成功，开始执行每日抓取。")

        self.stdout.write(self.style.WARNING("今日尚未完全抓取成功，开始执行每日抓取..."))
        result = call_command(
            "run_daily_pipeline",
            "--limit",
            str(options["limit"]),
            "--source",
            options["source"],
            "--region",
            options["region"],
            "--failover-after-minutes",
            str(options["failover_after_minutes"]),
        )

        if bool(result):
            now = timezone.now()
            for platform, checkpoint in checkpoints.items():
                run = DailyWorkflowRun.objects.filter(platform=platform, run_date=today).first()
                if not run or run.fetch_status != WorkflowStatus.SUCCESS:
                    mark_step(platform, "fetch", WorkflowStatus.SUCCESS, "今日抓取成功。")
                checkpoint.last_success_date = today
                checkpoint.last_success_at = now
                checkpoint.save(update_fields=["last_success_date", "last_success_at", "updated_at"])
            self.stdout.write(self.style.SUCCESS(f"今日抓取完成，检查点已更新：{today}"))
            return "success"

        for platform in SOCIAL_PLATFORMS:
            mark_step(platform, "fetch", WorkflowStatus.FAILED, "本次抓取未成功，检查点不更新。")
        self.stdout.write(self.style.WARNING("本次抓取未成功，检查点不更新。"))
        return "failed"
