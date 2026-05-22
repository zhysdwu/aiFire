from __future__ import annotations

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connection
from django.db.utils import OperationalError, ProgrammingError
from django.utils import timezone

from apps.trends.models import DailyFetchCheckpoint, WorkflowStatus
from apps.trends.services.analytics import SOCIAL_PLATFORMS
from apps.trends.services.workflow import mark_step


class Command(BaseCommand):
    help = "Ensure only one successful fetch per day based on per-platform checkpoints."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=60)
        parser.add_argument("--source", type=str, default="official", choices=["official", "all", "legacy"])
        parser.add_argument("--region", type=str, default="US")
        parser.add_argument("--failover-after-minutes", type=int, default=30)

    @staticmethod
    def _checkpoint_table_exists() -> bool:
        table_name = DailyFetchCheckpoint._meta.db_table
        return table_name in connection.introspection.table_names()

    def _checkpoints(self):
        return {platform: DailyFetchCheckpoint.get_for_platform(platform) for platform in SOCIAL_PLATFORMS}

    def _mark_fetch_for_all(self, status: str, message: str = "") -> None:
        for platform in SOCIAL_PLATFORMS:
            mark_step(platform, "fetch", status, message)

    def handle(self, *args, **options):
        today = timezone.localdate()
        try:
            if not self._checkpoint_table_exists():
                self.stdout.write(self.style.WARNING("未检测到每日检查点表，请先执行数据库迁移：python manage.py migrate"))
                return False
            checkpoints = self._checkpoints()
        except (ProgrammingError, OperationalError):
            self.stdout.write(self.style.WARNING("数据库结构尚未更新，请先执行数据库迁移：python manage.py migrate"))
            return False

        if all(checkpoint.last_success_date == today for checkpoint in checkpoints.values()):
            self._mark_fetch_for_all(WorkflowStatus.SKIPPED, "今日已抓取成功，跳过。")
            self.stdout.write(self.style.SUCCESS(f"今日已抓取成功，跳过。日期：{today}"))
            return "skipped"

        self._mark_fetch_for_all(WorkflowStatus.RUNNING, "今日尚未抓取成功，开始执行每日抓取。")
        self.stdout.write(self.style.WARNING("今日尚未抓取成功，开始执行每日抓取..."))
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
            for checkpoint in checkpoints.values():
                checkpoint.last_success_date = today
                checkpoint.last_success_at = now
                checkpoint.save(update_fields=["last_success_date", "last_success_at", "updated_at"])
            self._mark_fetch_for_all(WorkflowStatus.SUCCESS, "今日抓取成功。")
            self.stdout.write(self.style.SUCCESS(f"今日抓取成功，检查点已更新：{today}"))
            return "success"

        self._mark_fetch_for_all(WorkflowStatus.FAILED, "本次抓取未成功，检查点不更新。")
        self.stdout.write(self.style.WARNING("本次抓取未成功，检查点不更新。"))
        return "failed"
