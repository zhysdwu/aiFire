from __future__ import annotations

import re
from typing import Iterable

from apps.trends.services.deepseek_client import DeepSeekClient

_WS = re.compile(r"\\s+")
_WORD_RE = re.compile(r"[a-z][a-z0-9']+", re.I)
_ALPHA_RE = re.compile(r"^[a-z][a-z0-9']*$", re.I)

_STOPWORDS = {
    "a",
    "an",
    "the",
    "of",
    "to",
    "in",
    "on",
    "at",
    "for",
    "with",
    "from",
    "by",
    "as",
    "into",
    "about",
    "over",
    "under",
    "through",
    "and",
    "or",
    "but",
    "if",
    "because",
    "while",
    "that",
    "this",
    "these",
    "those",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "how",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "can",
    "could",
    "would",
    "should",
    "do",
    "does",
    "did",
    "will",
    "just",
    "very",
    "really",
}

_ADJECTIVE_LIKE = {
    "viral",
    "trending",
    "aesthetic",
    "quiet",
    "luxury",
    "minimal",
    "smart",
    "budget",
    "daily",
    "fresh",
    "retro",
    "bold",
    "clean",
    "easy",
    "new",
}


# Keep keywords as noun-like tokens or adjective+noun / verb+noun pair.
def _is_acceptable_pair(words: list[str]) -> bool:
    if len(words) == 1:
        return True

    first, second = words[0], words[1]

    if first in _ADJECTIVE_LIKE:
        return True

    if first.endswith("ing"):
        return True

    if second.endswith("ing"):
        return False

    return True


def normalize_phrase(text: str) -> str:
    text = text.strip().lower()
    return _WS.sub(" ", text)


def _is_valid_keyword(phrase: str) -> bool:
    words = phrase.split()
    if not words or len(words) > 2:
        return False

    for word in words:
        if not _ALPHA_RE.match(word):
            return False
        if word in _STOPWORDS:
            return False

    if len(words) == 1 and len(words[0]) < 3:
        return False

    if not _is_acceptable_pair(words):
        return False

    return True


def extract_phrases_with_llm(client: DeepSeekClient, texts: Iterable[str]) -> list[str]:
    system = (
        "Extract English trend keywords from TikTok title/caption text. "
        "Output only keyword forms: adjective+noun, verb+noun, or single noun. "
        "Never include stopwords/prepositions/articles/conjunctions. "
        "Return JSON {\"phrases\":[...]} and keep each phrase 1-2 words, lowercase, no hashtags."
    )
    user = "INPUT:\n" + "\n".join(f"- {t[:280]}" for t in texts if t)
    obj = client.chat_json(system=system, user=user)

    phrases = [normalize_phrase(item) for item in obj.get("phrases", []) if isinstance(item, str)]
    phrases = [p for p in phrases if _is_valid_keyword(p)]

    seen = set()
    result = []
    for phrase in phrases:
        if phrase in seen:
            continue
        seen.add(phrase)
        result.append(phrase)
    return result


def extract_phrases_basic(texts: Iterable[str], top_k: int = 80) -> list[str]:
    counts: dict[str, int] = {}

    for text in texts:
        words = _WORD_RE.findall((text or "").lower())
        if not words:
            continue

        for n in (1, 2):
            for idx in range(0, len(words) - n + 1):
                phrase = " ".join(words[idx : idx + n])
                if len(phrase) < 3:
                    continue
                if not _is_valid_keyword(phrase):
                    continue
                counts[phrase] = counts.get(phrase, 0) + 1

    ranked = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    return [item[0] for item in ranked[:top_k]]
