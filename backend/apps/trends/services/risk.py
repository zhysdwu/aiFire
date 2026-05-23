import re

from apps.trends.models import RiskLevel

BLOCK_PATTERNS = [
    re.compile(r"\\b(nazi|kkk)\\b", re.I),
    re.compile(r"\\b(cocaine|heroin)\\b", re.I),
]

HIGH_PATTERNS = [
    re.compile(r"\\b(adult|nsfw|porn)\\b", re.I),
]


def assess_risk(text: str) -> str:
    content = text or ""
    for pattern in BLOCK_PATTERNS:
        if pattern.search(content):
            return RiskLevel.BLOCKED
    for pattern in HIGH_PATTERNS:
        if pattern.search(content):
            return RiskLevel.HIGH
    return RiskLevel.LOW

import json
from apps.trends.services.deepseek_client import DeepSeekClient

BATCH_SIZE = 30

AI_REVIEW_SYSTEM_PROMPT = (
    "You are a content safety auditor. Review the following English keywords and classify each.\n"
    "Check for these violation categories:\n"
    "- Political sensitivity, hate speech, violent extremism\n"
    "- Adult/sexual content\n"
    "- Drugs/controlled substances\n"
    "- Trademark/brand infringement\n\n"
    "For each keyword, output:\n"
    '- "SAFE" if no issues\n'
    '- "REVIEW" if uncertain or borderline (needs human review)\n'
    '- "BLOCK" if clearly violating\n'
    'Return a JSON object: {"keyword1": {"verdict": "SAFE|REVIEW|BLOCK", "reason": "brief reason"}, ...}\n'
    'Only return the JSON object, no other text.'
)


def ai_batch_assess(keywords: list[str]) -> dict[str, dict]:
    if not keywords:
        return {}
    results: dict[str, dict] = {}
    for i in range(0, len(keywords), BATCH_SIZE):
        batch = keywords[i : i + BATCH_SIZE]
        try:
            client = DeepSeekClient.from_env()
            user_prompt = "Keywords to review:\n" + "\n".join(
                f'{idx + 1}. "{kw}"' for idx, kw in enumerate(batch)
            )
            payload = client.chat_json(system=AI_REVIEW_SYSTEM_PROMPT, user=user_prompt)
            if isinstance(payload, dict):
                for kw in batch:
                    item = payload.get(kw, {})
                    verdict = (item.get("verdict") or "SAFE").upper()
                    reason = (item.get("reason") or "")[:200]
                    if verdict not in {"SAFE", "REVIEW", "BLOCK"}:
                        verdict = "SAFE"
                    results[kw] = {"verdict": verdict, "reason": reason}
        except Exception:
            for kw in batch:
                results[kw] = {"verdict": "SAFE", "reason": "AI unavailable, defaulting to safe"}
    return results


def apply_ai_verdict(phrase_text: str, verdict_data: dict, current_risk: str) -> str:
    if current_risk not in {RiskLevel.LOW, RiskLevel.PENDING_REVIEW}:
        return current_risk
    verdict = verdict_data.get("verdict", "SAFE").upper()
    if verdict == "BLOCK":
        return RiskLevel.BLOCKED
    elif verdict == "REVIEW":
        return RiskLevel.PENDING_REVIEW
    return RiskLevel.LOW