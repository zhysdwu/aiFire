from __future__ import annotations

from apps.trends.models import AssistantIntent, AssistantMessageLog, Phrase, Platform
from apps.trends.services.analytics import SOCIAL_PLATFORMS, build_analytics_overview
from apps.trends.services.deepseek_client import DeepSeekClient


def classify_intent(question: str) -> str:
    normalized = question.lower()
    if "compare" in normalized or "对比" in normalized or "比较" in normalized:
        return AssistantIntent.PLATFORM_COMPARE
    if "title" in normalized or "标题" in normalized:
        return AssistantIntent.TITLE_REFINE
    if "why" in normalized or "popular" in normalized or "为什么" in normalized or "趋势" in normalized:
        return AssistantIntent.TREND_ANALYSIS
    return AssistantIntent.GENERAL


def fallback_answer(platform: str, phrase: Phrase | None = None) -> str:
    target = phrase.text if phrase else platform
    return f"DeepSeek 暂时不可用。你仍可围绕 {target} 先比较热度、关键词覆盖和可转化为标题的表达。"


def normalize_platform(platform: str) -> str:
    value = (platform or Platform.TIKTOK).strip().lower()
    return value if value in SOCIAL_PLATFORMS else Platform.TIKTOK


def answer_assistant_question(platform: str, question: str, phrase_id: int | None, user=None) -> dict:
    platform = normalize_platform(platform)
    phrase = Phrase.objects.filter(id=phrase_id).first() if phrase_id else None
    intent = classify_intent(question)
    answer = fallback_answer(platform, phrase)
    suggestions = ["对比平台表现", "生成标题变体"]

    try:
        payload = DeepSeekClient.from_env().chat_json(
            system="You are a social trend analyst. Return JSON with answer and suggestions.",
            user=(
                f"PLATFORM={platform}\n"
                f"PHRASE={phrase.text if phrase else ''}\n"
                f"QUESTION={question}\n"
                f"OVERVIEW={build_analytics_overview()}"
            ),
        )
        answer = (payload.get("answer") or answer).strip()
        suggestions = payload.get("suggestions") or suggestions
    except Exception:
        pass

    AssistantMessageLog.objects.create(
        platform=platform,
        phrase=phrase,
        question=question,
        answer=answer,
        intent=intent,
        created_by=user if getattr(user, "is_authenticated", False) else None,
    )
    return {"intent": intent, "answer": answer, "suggestions": suggestions}
