from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.trends.models import EvidenceLink, GeneratedTitle, Phrase, PhraseDeleteLog, PhraseMetricWindow, TikTokRawSnapshot


class Command(BaseCommand):
    help = "Delete generated keyword entities and rebuild from snapshots using pipeline"

    def add_arguments(self, parser):
        parser.add_argument("--seed-demo", action="store_true")
        parser.add_argument("--limit", type=int, default=60)
        parser.add_argument("--source", type=str, default="official", choices=["official", "all", "legacy"])
        parser.add_argument("--region", type=str, default="US")
        parser.add_argument("--clear-snapshots", action="store_true")
        parser.add_argument("--failover-after-minutes", type=int, default=30)

    def handle(self, *args, **options):
        if options["clear_snapshots"]:
            TikTokRawSnapshot.objects.all().delete()

        EvidenceLink.objects.all().delete()
        GeneratedTitle.objects.all().delete()
        PhraseMetricWindow.objects.all().delete()
        PhraseDeleteLog.objects.all().delete()
        Phrase.objects.all().delete()

        args = [
            "run_daily_pipeline",
            "--limit",
            str(options["limit"]),
            "--source",
            options["source"],
            "--region",
            options["region"],
            "--failover-after-minutes",
            str(options["failover_after_minutes"]),
        ]
        if options["seed_demo"]:
            args.append("--seed-demo")

        from django.core.management import call_command

        call_command(*args)
        self.stdout.write(self.style.SUCCESS("关键词库已重建。"))
