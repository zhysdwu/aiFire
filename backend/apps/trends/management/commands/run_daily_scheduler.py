from __future__ import annotations

import time

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Run a lightweight in-process scheduler: ensure one fetch per day while project is running."

    def add_arguments(self, parser):
        parser.add_argument("--check-interval-minutes", type=int, default=15)
        parser.add_argument("--source", type=str, default="official", choices=["official", "all", "legacy"])
        parser.add_argument("--limit", type=int, default=60)
        parser.add_argument("--region", type=str, default="US")
        parser.add_argument("--failover-after-minutes", type=int, default=30)

    def handle(self, *args, **options):
        interval_minutes = max(1, int(options["check_interval_minutes"]))
        interval_seconds = interval_minutes * 60

        self.stdout.write(
            self.style.SUCCESS(
                f"每日抓取调度器已启动（{timezone.localtime().strftime('%Y-%m-%d %H:%M:%S')}），"
                f"检查间隔 {interval_minutes} 分钟。"
            )
        )

        try:
            while True:
                try:
                    call_command(
                        "ensure_daily_fetch",
                        "--source",
                        options["source"],
                        "--limit",
                        str(options["limit"]),
                        "--region",
                        options["region"],
                        "--failover-after-minutes",
                        str(options["failover_after_minutes"]),
                    )
                except Exception as exc:
                    self.stdout.write(self.style.WARNING(f"每日抓取检查执行异常：{exc}"))
                time.sleep(interval_seconds)
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("每日抓取调度器已停止。"))
