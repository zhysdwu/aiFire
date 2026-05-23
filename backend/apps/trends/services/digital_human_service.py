from __future__ import annotations

import uuid

from apps.trends.models import AssistantMessageLog, DigitalHumanSessionLog, Phrase
from apps.trends.services.assistant_core import ask_deepseek, classify_intent, normalize_platform
from apps.trends.services.livetalking_client import trigger_livetalking


def answer_with_digital_human(platform: str, question: str, phrase_id, user=None) -> dict:
    normalized_platform = normalize_platform(platform)
    intent = classify_intent(question)
    trace_id = str(uuid.uuid4())

    phrase = None
    if phrase_id not in {"", None}:
        try:
            phrase = Phrase.objects.filter(id=int(phrase_id)).first()
        except (TypeError, ValueError):
            phrase = None

    ai_result = ask_deepseek(question=question, platform=normalized_platform, intent=intent)
    answer = ai_result["answer"]
    highlights = ai_result["highlights"]
    final_intent = ai_result.get("intent") or intent
    provider = ai_result.get("provider") or "fallback"
    safe_provider = str(provider)[:32]

    AssistantMessageLog.objects.create(
        platform=normalized_platform,
        phrase=phrase,
        question=question,
        answer=answer,
        intent=final_intent,
        created_by=user if getattr(user, "is_authenticated", False) else None,
    )

    livetalking = trigger_livetalking(answer=answer, trace_id=trace_id)
    DigitalHumanSessionLog.objects.create(
        platform=normalized_platform,
        phrase=phrase,
        question=question,
        answer=answer,
        intent=final_intent,
        provider=safe_provider,
        session_id="",
        trace_id=trace_id,
        livetalking_status=livetalking.get("status", "skipped"),
        livetalking_message=livetalking.get("message", ""),
        created_by=user if getattr(user, "is_authenticated", False) else None,
    )
    return {
        "answer": answer,
        "highlights": highlights,
        "intent": final_intent,
        "provider": provider,
        "livetalking": livetalking,
        "trace_id": trace_id,
    }
