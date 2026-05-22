from __future__ import annotations

from django.db.models import Avg

from apps.trends.models import Phrase, Platform, RiskLevel, Window


SOCIAL_PLATFORMS = [Platform.TIKTOK, Platform.INSTAGRAM, Platform.FACEBOOK]


def build_analytics_overview() -> dict:
    platform_rows = []
    for platform in SOCIAL_PLATFORMS:
        phrases = Phrase.objects.filter(platform=platform, is_deleted=False).exclude(risk_level=RiskLevel.BLOCKED)
        avg_heat = phrases.filter(metrics__window=Window.H24).aggregate(value=Avg("metrics__heat_score"))["value"] or 0
        top_keywords = list(phrases.order_by("-last_seen_at", "-created_at").values_list("text", flat=True)[:5])
        last_updated_at = phrases.order_by("-last_seen_at").values_list("last_seen_at", flat=True).first()
        platform_rows.append(
            {
                "platform": platform,
                "total_phrases": phrases.count(),
                "avg_heat_score": round(float(avg_heat), 2),
                "top_keywords": top_keywords,
                "last_updated_at": last_updated_at,
            }
        )

    highest_heat = max(platform_rows, key=lambda item: item["avg_heat_score"], default=None)
    most_keywords = max(platform_rows, key=lambda item: item["total_phrases"], default=None)
    return {
        "platforms": platform_rows,
        "comparison": {
            "highest_heat_platform": highest_heat["platform"] if highest_heat else "",
            "most_keywords_platform": most_keywords["platform"] if most_keywords else "",
        },
    }
