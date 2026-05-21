from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from typing import Any

from django.core.management.base import BaseCommand
from django.db.models import Max
from django.utils import timezone

from apps.trends.models import (
    DataSourceStatus,
    EvidenceLink,
    GeneratedTitle,
    Phrase,
    PhraseMetricWindow,
    Platform,
    RiskLevel,
    TikTokRawSnapshot,
    Window,
)
from apps.trends.services.deepseek_client import DeepSeekClient
from apps.trends.services.phrase_extractor import (
    _is_valid_keyword,
    extract_phrases_basic,
    extract_phrases_with_llm,
)
from apps.trends.services.risk import assess_risk
from apps.trends.services.source_collectors import (
    fetch_answer_the_public_terms_from_csv,
    fetch_google_trends_terms,
    fetch_tiktok_creative_center_hashtags,
)
from apps.trends.services.tiktok_scraper import fetch_tiktok_trending
from apps.trends.services.title_generator import generate_titles_basic, generate_titles_for_phrase


CollectorFunc = Callable[[int, str], list[dict[str, Any]]]


def _int_metric(snapshot: TikTokRawSnapshot, key: str) -> int:
    value = (snapshot.raw_metrics or {}).get(key)
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _compute_heat_score(snapshot: TikTokRawSnapshot) -> int:
    views = _int_metric(snapshot, "playCount") or _int_metric(snapshot, "views")
    likes = _int_metric(snapshot, "diggCount")
    comments = _int_metric(snapshot, "commentCount")
    shares = _int_metric(snapshot, "shareCount")

    raw = (views / 50000.0) * 60 + (likes / 5000.0) * 20 + (comments / 800.0) * 12 + (shares / 300.0) * 8
    return max(0, min(100, int(raw)))


def _score_explain(snapshot: TikTokRawSnapshot) -> str:
    views = _int_metric(snapshot, "playCount") or _int_metric(snapshot, "views")
    likes = _int_metric(snapshot, "diggCount")
    comments = _int_metric(snapshot, "commentCount")
    source_name = snapshot.get_platform_display()
    return f"{source_name}数据：播放{views}、点赞{likes}、评论{comments}综合计算。"


def _unique_snapshots(items: list[dict], limit: int) -> list[dict]:
    seen: set[tuple[str, str]] = set()
    out: list[dict] = []
    for item in items:
        platform = str(item.get("platform") or Platform.TIKTOK)
        external_id = str(item.get("external_id") or "").strip()
        if not external_id:
            continue
        key = (platform, external_id)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
        if len(out) >= limit:
            break
    return out


def _upsert_source_status(
    source_key: str,
    display_name: str,
    platform: str,
    success: bool,
    count: int,
    error_message: str = "",
) -> None:
    now = timezone.now()
    status_obj, created = DataSourceStatus.objects.get_or_create(
        source_key=source_key,
        defaults={
            "display_name": display_name,
            "platform": platform,
        },
    )

    status_obj.display_name = display_name
    status_obj.platform = platform
    status_obj.last_attempt_at = now
    status_obj.last_success = success
    status_obj.last_count = max(0, int(count))

    if success:
        status_obj.last_success_at = now
        status_obj.error_message = ""
        status_obj.consecutive_failures = 0
        status_obj.first_failure_at = None
    else:
        status_obj.error_message = (error_message or "")[:2000]
        status_obj.consecutive_failures = (0 if created else status_obj.consecutive_failures) + 1
        if status_obj.first_failure_at is None:
            status_obj.first_failure_at = now

    status_obj.save()


def _is_source_locked(status: DataSourceStatus | None, failover_after_minutes: int) -> bool:
    if not status:
        return False
    if status.consecutive_failures <= 0:
        return False
    if status.first_failure_at is None:
        return False
    if failover_after_minutes <= 0:
        return True
    delta = timezone.now() - status.first_failure_at
    return delta < timedelta(minutes=failover_after_minutes)


class Command(BaseCommand):
    help = "Run daily pipeline: collect -> extract -> score -> generate"

    def add_arguments(self, parser):
        parser.add_argument("--seed-demo", action="store_true")
        parser.add_argument("--limit", type=int, default=60)
        parser.add_argument("--source", type=str, default="official", choices=["official", "all", "legacy"])
        parser.add_argument("--region", type=str, default="US")
        parser.add_argument("--failover-after-minutes", type=int, default=30)

    def _collect_with_failover(self, limit: int, region: str, failover_after_minutes: int) -> list[dict[str, Any]]:
        def _collect_tiktok_cc(_limit: int, _region: str) -> list[dict[str, Any]]:
            return fetch_tiktok_creative_center_hashtags(limit=_limit, region=_region)

        def _collect_google_trends(_limit: int, _region: str) -> list[dict[str, Any]]:
            return fetch_google_trends_terms(limit=_limit, geo=_region)

        def _collect_answer_the_public(_limit: int, _region: str) -> list[dict[str, Any]]:
            return fetch_answer_the_public_terms_from_csv(limit=_limit)

        def _collect_tiktok_legacy(_limit: int, _region: str) -> list[dict[str, Any]]:
            items = fetch_tiktok_trending(limit=_limit, region=_region)
            for item in items:
                item["platform"] = Platform.TIKTOK
                item["region"] = _region
            return items

        pipelines: list[tuple[str, str, str, CollectorFunc]] = [
            ("tiktok_creative_center", "TikTok Creative Center", Platform.TIKTOK, _collect_tiktok_cc),
            ("google_trends", "Google Trends", Platform.GOOGLE_TRENDS, _collect_google_trends),
            ("answer_the_public", "AnswerThePublic(CSV)", Platform.ANSWER_THE_PUBLIC, _collect_answer_the_public),
            ("tiktok_legacy", "TikTok网页抓取(兜底)", Platform.TIKTOK, _collect_tiktok_legacy),
        ]

        status_map = {item.source_key: item for item in DataSourceStatus.objects.filter(source_key__in=[p[0] for p in pipelines])}

        ordered: list[tuple[str, str, str, CollectorFunc]] = []
        locked: list[tuple[str, str, str, CollectorFunc]] = []
        for pipe in pipelines:
            key = pipe[0]
            status = status_map.get(key)
            if _is_source_locked(status, failover_after_minutes):
                locked.append(pipe)
            else:
                ordered.append(pipe)

        all_items: list[dict[str, Any]] = []
        for source_key, display_name, platform, collector in ordered:
            try:
                items = collector(limit, region)
                if not items:
                    _upsert_source_status(source_key, display_name, platform, False, 0, "采集结果为空")
                    continue
                for item in items:
                    item["platform"] = item.get("platform") or platform
                    item["region"] = item.get("region") or region
                _upsert_source_status(source_key, display_name, platform, True, len(items))
                all_items.extend(items)
                if len(all_items) >= limit:
                    break
            except Exception as exc:
                self.stdout.write(self.style.WARNING(f"{display_name}采集失败: {exc}"))
                _upsert_source_status(source_key, display_name, platform, False, 0, str(exc))
                continue

        if all_items:
            return all_items

        for source_key, display_name, platform, collector in locked:
            try:
                items = collector(limit, region)
                if not items:
                    _upsert_source_status(source_key, display_name, platform, False, 0, "采集结果为空")
                    continue
                for item in items:
                    item["platform"] = item.get("platform") or platform
                    item["region"] = item.get("region") or region
                _upsert_source_status(source_key, display_name, platform, True, len(items))
                all_items.extend(items)
                if len(all_items) >= limit:
                    break
            except Exception as exc:
                self.stdout.write(self.style.WARNING(f"{display_name}采集失败: {exc}"))
                _upsert_source_status(source_key, display_name, platform, False, 0, str(exc))
                continue
        return all_items

    def handle(self, *args, **options):
        limit = max(20, int(options["limit"]))
        source_mode = options["source"]
        region = (options["region"] or "US").upper()
        failover_after_minutes = max(0, int(options["failover_after_minutes"]))
        run_started = timezone.now()

        if options["seed_demo"]:
            seed_keywords = [
                "quiet luxury",
                "minimal makeup",
                "street style",
                "clean girl",
                "retro denim",
                "summer outfit",
                "daily skincare",
                "budget haul",
                "viral dance",
                "fitness routine",
                "core workout",
                "meal prep",
                "healthy snacks",
                "travel vlog",
                "city guide",
                "weekend trip",
                "study setup",
                "desk decor",
                "notion template",
                "ai tools",
                "prompt design",
                "coding tips",
                "startup story",
                "creator economy",
                "product review",
                "unboxing video",
                "pet routine",
                "cat tricks",
                "dog training",
                "home decor",
                "cozy room",
                "kitchen hacks",
                "morning routine",
                "night routine",
                "hair tutorial",
                "nail design",
                "fashion inspo",
                "capsule wardrobe",
                "camera settings",
                "editing workflow",
                "photo ideas",
                "mindset shift",
                "confidence boost",
                "career advice",
                "interview prep",
                "side hustle",
                "money habits",
                "book summary",
                "language tips",
                "productivity hacks",
                "focus music",
                "study motivation",
                "meditation guide",
                "yoga flow",
                "running plan",
                "meal ideas",
                "vegan recipes",
                "coffee recipe",
                "matcha latte",
                "sneaker styling",
                "thrift finds",
                "festival look",
                "party makeup",
                "date outfit",
                "winter layering",
                "travel essentials",
                "packing list",
                "airport outfit",
                "beach vibes",
                "sunset photos",
                "phone tricks",
                "app tutorial",
                "workflow setup",
                "remote work",
                "team culture",
                "presentation tips",
                "marketing ideas",
                "content strategy",
                "brand building",
                "video hooks",
                "storytelling tips",
                "engagement tips",
            ]
            for idx, keyword in enumerate(seed_keywords, start=1):
                views = 180000 - (idx * 1300)
                likes = 18000 - (idx * 120)
                comments = 1700 - (idx * 8)
                shares = 900 - (idx * 5)
                TikTokRawSnapshot.objects.create(
                    platform=Platform.TIKTOK,
                    region=region,
                    source_url=f"https://example.com/tiktok/demo{idx}",
                    external_id=f"demo{idx}",
                    title_text=f"{keyword} trend is booming",
                    caption_text=f"new {keyword} ideas for creators",
                    raw_metrics={
                        "views": max(5000, views),
                        "diggCount": max(500, likes),
                        "commentCount": max(40, comments),
                        "shareCount": max(20, shares),
                    },
                )
            _upsert_source_status("seed_demo", "演示数据", Platform.TIKTOK, True, len(seed_keywords))
        else:
            collected: list[dict[str, Any]] = []
            if source_mode == "official":
                collected = self._collect_with_failover(limit=limit, region=region, failover_after_minutes=failover_after_minutes)
            elif source_mode == "all":
                collected = self._collect_with_failover(limit=max(limit * 2, 120), region=region, failover_after_minutes=0)
            else:
                try:
                    legacy = fetch_tiktok_trending(limit=limit, region=region)
                    for item in legacy:
                        item["platform"] = Platform.TIKTOK
                        item["region"] = region
                    collected.extend(legacy)
                    _upsert_source_status("tiktok_legacy", "TikTok网页抓取(兜底)", Platform.TIKTOK, True, len(legacy))
                except Exception as exc:
                    self.stdout.write(self.style.WARNING(f"TikTok网页抓取失败，将仅使用已有快照: {exc}"))
                    _upsert_source_status("tiktok_legacy", "TikTok网页抓取(兜底)", Platform.TIKTOK, False, 0, str(exc))

            collected = _unique_snapshots(collected, limit=max(limit * 3, 180))
            for item in collected:
                platform = str(item.get("platform") or Platform.TIKTOK)
                TikTokRawSnapshot.objects.get_or_create(
                    platform=platform,
                    external_id=item["external_id"],
                    defaults={
                        "region": item.get("region") or region,
                        "source_url": item["source_url"],
                        "title_text": item.get("title_text") or "",
                        "caption_text": item.get("caption_text") or "",
                        "raw_metrics": item.get("raw_metrics") or {},
                    },
                )

        snapshots_qs = TikTokRawSnapshot.objects.filter(fetched_at__gte=run_started).order_by("-fetched_at")
        if not snapshots_qs.exists():
            snapshots_qs = TikTokRawSnapshot.objects.order_by("-fetched_at")
        snapshots = list(snapshots_qs[: max(limit * 3, 180)])
        if not snapshots:
            self.stdout.write(self.style.WARNING("没有可用快照数据，任务结束。"))
            return

        texts = [item.title_text for item in snapshots] + [item.caption_text for item in snapshots]

        client = None
        use_ai = True
        phrases_ai: list[str] = []
        try:
            client = DeepSeekClient.from_env()
            phrases_ai = extract_phrases_with_llm(client, texts)
        except Exception:
            use_ai = False

        phrases_basic = extract_phrases_basic(texts, top_k=200)
        merged_phrases: list[str] = []
        seen_phrases: set[str] = set()
        for phrase in (phrases_ai + phrases_basic):
            if phrase in seen_phrases:
                continue
            if not _is_valid_keyword(phrase):
                continue
            seen_phrases.add(phrase)
            merged_phrases.append(phrase)
            if len(merged_phrases) >= 100:
                break

        phrases = merged_phrases[:100]
        if not phrases:
            self.stdout.write(self.style.WARNING("未提取到有效关键词，任务结束。"))
            return

        now = timezone.now()
        metric_by_phrase: dict[str, dict] = {}
        for snapshot in snapshots:
            merged_text = " ".join([snapshot.title_text or "", snapshot.caption_text or ""]).lower()
            score = _compute_heat_score(snapshot)
            explain = _score_explain(snapshot)
            for phrase_text in phrases:
                if phrase_text not in merged_text:
                    continue
                existing = metric_by_phrase.get(phrase_text)
                if not existing or score > existing["score"]:
                    metric_by_phrase[phrase_text] = {
                        "score": score,
                        "explain": explain,
                        "url": snapshot.source_url,
                        "title": (snapshot.title_text or "")[:255],
                    }

        for phrase_text in phrases:
            metric = metric_by_phrase.get(phrase_text)
            if not metric:
                continue

            phrase_risk = assess_risk(phrase_text)
            phrase, _ = Phrase.objects.get_or_create(text=phrase_text, defaults={"risk_level": phrase_risk})
            phrase.first_seen_at = phrase.first_seen_at or now
            phrase.last_seen_at = now
            phrase.risk_level = phrase_risk
            phrase.is_deleted = False
            phrase.deleted_at = None
            phrase.deleted_reason_type = ""
            phrase.deleted_reason_text = ""
            phrase.deleted_by = None
            phrase.save(
                update_fields=[
                    "first_seen_at",
                    "last_seen_at",
                    "risk_level",
                    "is_deleted",
                    "deleted_at",
                    "deleted_reason_type",
                    "deleted_reason_text",
                    "deleted_by",
                ]
            )

            EvidenceLink.objects.get_or_create(
                phrase=phrase,
                url=metric["url"],
                defaults={"title": metric["title"]},
            )

            previous_metric = phrase.metrics.filter(window=Window.H24).order_by("-computed_at").first()
            growth_prev = None
            if previous_metric and previous_metric.heat_score:
                growth_prev = round(((metric["score"] - previous_metric.heat_score) / previous_metric.heat_score) * 100, 2)

            hist_agg = phrase.metrics.filter(window=Window.H24).aggregate(max_score=Max("heat_score"))
            max_hist = hist_agg.get("max_score") or metric["score"]
            growth_7d = round(((metric["score"] - max_hist) / max_hist) * 100, 2) if max_hist else 0

            PhraseMetricWindow.objects.update_or_create(
                phrase=phrase,
                window=Window.H24,
                defaults={
                    "heat_score": metric["score"],
                    "growth_prev_window": growth_prev,
                    "growth_vs_7d_avg": growth_7d,
                    "score_explain": metric["explain"] if use_ai else f"规则评分: {metric['explain']}",
                },
            )

            if phrase.risk_level == RiskLevel.BLOCKED:
                continue

            if client:
                try:
                    generated_items = generate_titles_for_phrase(client, phrase=phrase_text, n=3)
                except Exception:
                    generated_items = generate_titles_basic(phrase_text, n=3)
            else:
                generated_items = generate_titles_basic(phrase_text, n=3)

            GeneratedTitle.objects.filter(phrase=phrase).delete()
            for item in generated_items:
                output_risk = assess_risk(f"{item['title']} {item['caption']}")
                GeneratedTitle.objects.create(
                    phrase=phrase,
                    window=Window.D30,
                    title=item["title"],
                    caption=item["caption"],
                    template=item["template"],
                    risk_level=output_risk,
                    is_published=(output_risk != RiskLevel.BLOCKED),
                )

        self.stdout.write(self.style.SUCCESS("Daily pipeline done"))
