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
