from __future__ import annotations

import json
import logging

import requests
import traceback

from django.db.models import Avg, Max, Q
from apps.trends.models import AssistantIntent, Phrase, Platform, RiskLevel, Window
from apps.trends.services.deepseek_client import DeepSeekClient


logger = logging.getLogger(__name__)

SOCIAL_PLATFORMS = {Platform.TIKTOK, Platform.INSTAGRAM, Platform.FACEBOOK, Platform.YOUTUBE}


def normalize_platform(platform: str) -> str:
    value = (platform or Platform.TIKTOK).strip().lower()
    return value if value in SOCIAL_PLATFORMS else Platform.TIKTOK


def classify_intent(question: str) -> str:
    normalized = (question or "").lower()
    if "compare" in normalized or "对比" in normalized or "比较" in normalized:
        return AssistantIntent.PLATFORM_COMPARE
    if "title" in normalized or "标题" in normalized or "推荐" in normalized or "热词" in normalized or "排行" in normalized or "hot" in normalized:
        return AssistantIntent.TITLE_REFINE
    if "why" in normalized or "趋势" in normalized or "分析" in normalized or "值得做" in normalized:
        return AssistantIntent.TREND_ANALYSIS
    return AssistantIntent.GENERAL


def _build_hotwords_context(platform: str) -> str:
    """Build a structured summary of hot phrases with heat scores and example titles."""
    phrases = Phrase.objects.filter(
        platform=platform, is_deleted=False
    ).exclude(risk_level=RiskLevel.BLOCKED)

    if not phrases.exists():
        return f"(No hot phrases data available for {platform} yet)"

    top_phrases = list(
        phrases.annotate(
            heat_24h=Avg("metrics__heat_score", filter=Q(metrics__window=Window.H24)),
            heat_7d=Avg("metrics__heat_score", filter=Q(metrics__window=Window.D7)),
        ).order_by("-last_seen_at")[:30]
    )

    lines = [f"=== {platform.upper()} HOT PHRASES RANKING ==="]
    for i, p in enumerate(top_phrases, 1):
        heat_24h = int(p.heat_24h) if p.heat_24h else 0
        heat_7d = int(p.heat_7d) if p.heat_7d else 0
        trend = "↑" if heat_24h > heat_7d else ("↓" if heat_24h < heat_7d else "→")
        lines.append(f"#{i} {p.text} | 24h热度:{heat_24h} 7d热度:{heat_7d} 趋势:{trend}")

    # Append example generated titles for top phrases
    from apps.trends.models import GeneratedTitle
    top_texts = [p.text for p in top_phrases[:10]]
    sample_titles = GeneratedTitle.objects.filter(
        phrase__text__in=top_texts, is_published=True
    ).values_list("title", flat=True)[:15]
    if sample_titles:
        lines.append("")
        lines.append("=== EXAMPLE HIGH-PERFORMANCE TITLES ===")
        for t in sample_titles:
            lines.append(f"- {t}")

    lines.append("")
    lines.append(f"Total active phrases: {phrases.count()}")
    return "\n".join(lines)


def _fallback_result(intent: str, platform: str, question: str) -> dict:
    short_q = question[:40] + "…" if len(question) > 40 else question
    answer = f"关于「{short_q}」：建议围绕 {platform} 先做小规模验证，这个问题有内容机会。"
    highlights = [
        "先用最近7天数据验证需求热度变化。",
        "优先测试低成本内容样式并对比完播与互动。",
        "保留1-2个备选方向，避免单点押注。",
    ]
    if intent == AssistantIntent.PLATFORM_COMPARE:
        answer = "结论：建议先比较平台流量结构，再决定主发阵地。"
    elif intent == AssistantIntent.TITLE_REFINE:
        answer = "结论：建议先保留核心关键词，再强化场景和收益表达。"
    elif intent == AssistantIntent.TREND_ANALYSIS:
        answer = "结论：该方向可做，但需先验证增长是否可持续。"
    return {
        "answer": answer,
        "highlights": highlights,
        "intent": intent,
        "provider": "fallback",
        "error": question[:0],
    }


def _extract_highlights(payload: dict) -> list[str]:
    highlights = payload.get("highlights") or payload.get("suggestions") or []
    if not isinstance(highlights, list):
        return []
    normalized = [str(item).strip() for item in highlights if str(item).strip()]
    return normalized[:3]


def ask_deepseek(question: str, platform: str, intent: str) -> dict:
    fallback = _fallback_result(intent=intent, platform=platform, question=question)
    try:
        hotwords_context = _build_hotwords_context(platform)
        payload = DeepSeekClient.from_env().chat_json(
            system=(
                "You are a social media hot-trend analyst and title strategist. "
                "You have access to REAL hot phrases ranking, heat scores, and example titles. "
                "Your job: analyze the data, answer user questions, and recommend high-heat titles. "
                "When recommending titles, use concrete examples from the data. "
                "Return JSON with fields: answer(string, concise analysis), highlights(array of 3 actionable tips), intent(string)."
            ),
            user=(
                f"PLATFORM={platform}\n"
                f"INTENT={intent}\n"
                f"QUESTION={question}\n"
                f"{hotwords_context}"
            ),
        )
        answer = str(payload.get("answer") or "").strip() or fallback["answer"]
        highlights = _extract_highlights(payload) or fallback["highlights"]
        model_intent = str(payload.get("intent") or intent).strip() or intent
        return {
            "answer": answer,
            "highlights": highlights,
            "intent": model_intent,
            "provider": "deepseek",
            "error": None,
        }
    except Exception as exc:
        import traceback as _tb
        err_detail = f"{type(exc).__name__}: {exc}"
        logger.warning("DeepSeek request failed: %s", err_detail, exc_info=True)
        fallback["error"] = err_detail[:200]
        return fallback