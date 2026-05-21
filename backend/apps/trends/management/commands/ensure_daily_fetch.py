from __future__ import annotations

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.trends.models import TikTokRawSnapshot


class Command(BaseCommand):
    help = "Ensure today has at least one fetch; if not, run run_daily_pipeline once."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=60)
        parser.add_argument("--source", type=str, default="official", choices=["official", "all", "legacy"])
        parser.add_argument("--region", type=str, default="US")
        parser.add_argument("--failover-after-minutes", type=int, default=30)

    def handle(self, *args, **options):
        today = timezone.localdate()
        has_today_data = TikTokRawSnapshot.objects.filter(fetched_at__date=today).exists()

        if has_today_data:
            latest = (
                TikTokRawSnapshot.objects.filter(fetched_at__date=today)
                .order_by("-fetched_at")
                .values_list("fetched_at", flat=True)
                .first()
            )
            self.stdout.write(self.style.SUCCESS(f"今日已抓取，跳过。最近一次：{latest}"))
            return

        self.stdout.write(self.style.WARNING("今日尚未抓取，开始执行每日抓取..."))
        call_command(
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
        self.stdout.write(self.style.SUCCESS("今日抓取完成。"))
