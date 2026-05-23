from __future__ import annotations

import json
import logging

import requests

from apps.trends.models import AssistantIntent, AssistantMessageLog, Phrase, Platform
from apps.trends.services.analytics import SOCIAL_PLATFORMS, build_analytics_overview
from apps.trends.services.deepseek_client import DeepSeekClient


logger = logging.getLogger(__name__)

PLATFORM_LABELS = {
    Platform.TIKTOK: "TikTok",
    Platform.INSTAGRAM: "Instagram",
    Platform.FACEBOOK: "Facebook",
    Platform.YOUTUBE: "YouTube",
}


def classify_intent(question: str) -> str:
    normalized = question.lower()
    if "compare" in normalized or "对比" in normalized or "比较" in normalized:
        return AssistantIntent.PLATFORM_COMPARE
    if (
        "why" in normalized
        or "popular" in normalized
        or "为什么" in normalized
        or "趋势" in normalized
        or "分析" in normalized
    ):
        return AssistantIntent.TREND_ANALYSIS
    if "title" in normalized or "标题" in normalized:
        return AssistantIntent.TITLE_REFINE
    return AssistantIntent.GENERAL


def fallback_answer(platform: str, phrase: Phrase | None = None, intent: str = AssistantIntent.GENERAL) -> str:
    target = phrase.text if phrase else PLATFORM_LABELS.get(platform, platform)
    if intent == AssistantIntent.PLATFORM_COMPARE:
        return f"基于当前已采集数据，可先对比 {target} 与其他平台的热度、增长和标题转化空间。"
    if intent == AssistantIntent.TITLE_REFINE:
        return f"基于当前已采集数据，可围绕 {target} 生成更具体、更有场景感的标题变体。"
    if intent == AssistantIntent.TREND_ANALYSIS:
        return f"基于当前已采集数据，{target} 的分析重点应放在热度来源、受众兴趣和可转化的内容角度。"
    return f"基于当前已采集数据，建议先围绕 {target} 比较热度、关键词覆盖和可转化为标题的表达。"


def fallback_suggestions(intent: str) -> list[str]:
    if intent == AssistantIntent.PLATFORM_COMPARE:
        return ["对比三个平台表现", "找出增长最快的平台"]
    if intent == AssistantIntent.TITLE_REFINE:
        return ["生成 5 个标题变体", "根据反馈改写标题"]
    if intent == AssistantIntent.TREND_ANALYSIS:
        return ["解释爆火原因", "给出内容创作切入点"]
    return ["对比平台表现", "生成标题变体"]


def explain_deepseek_error(exc: Exception) -> tuple[str, str]:
    if isinstance(exc, RuntimeError) and "Missing DEEPSEEK_API_KEY" in str(exc):
        return "missing_api_key", "DeepSeek API Key 未配置：请在 backend/.env 填写 DEEPSEEK_API_KEY 后重启后端。"

    if isinstance(exc, requests.HTTPError):
        status_code = exc.response.status_code if exc.response is not None else None
        if status_code in {401, 403}:
            return "invalid_api_key", "DeepSeek 鉴权失败：请检查 DEEPSEEK_API_KEY 是否正确、是否已开通可用额度。"
        if status_code == 429:
            return "rate_limited", "DeepSeek 请求过于频繁或额度受限：请稍后重试或检查账户额度。"
        return "http_error", f"DeepSeek 接口返回异常状态：{status_code or '未知'}。"

    if isinstance(exc, (requests.Timeout, requests.ConnectionError)):
        return "network_error", "DeepSeek 网络连接失败：请检查本机网络、代理或防火墙设置。"

    if isinstance(exc, (json.JSONDecodeError, KeyError, TypeError)):
        return "invalid_response", "DeepSeek 返回格式不符合预期：已记录后端日志，需检查模型响应内容。"

    return "unknown_error", "DeepSeek 调用失败：请查看后端日志中的具体异常。"


def normalize_platform(platform: str) -> str:
    value = (platform or Platform.TIKTOK).strip().lower()
    return value if value in SOCIAL_PLATFORMS else Platform.TIKTOK


def answer_assistant_question(platform: str, question: str, phrase_id: int | None, user=None) -> dict:
    platform = normalize_platform(platform)
    phrase = Phrase.objects.filter(id=phrase_id).first() if phrase_id else None
    intent = classify_intent(question)
    answer = fallback_answer(platform, phrase, intent)
    suggestions = fallback_suggestions(intent)
    ai_status = "fallback"
    ai_error_code = None
    ai_error_message = None

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
        ai_status = "deepseek"
    except Exception as exc:
        ai_error_code, ai_error_message = explain_deepseek_error(exc)
        logger.warning("DeepSeek assistant failed: %s", ai_error_code, exc_info=True)

    AssistantMessageLog.objects.create(
        platform=platform,
        phrase=phrase,
        question=question,
        answer=answer,
        intent=intent,
        created_by=user if getattr(user, "is_authenticated", False) else None,
    )
    return {
        "intent": intent,
        "answer": answer,
        "suggestions": suggestions,
        "ai_status": ai_status,
        "ai_error_code": ai_error_code,
        "ai_error_message": ai_error_message,
    }
