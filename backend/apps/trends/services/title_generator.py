from __future__ import annotations

from apps.trends.services.deepseek_client import DeepSeekClient


def generate_titles_for_phrase(client: DeepSeekClient, phrase: str, n: int = 3) -> list[dict]:
    system = (
        "You generate TikTok English titles and one-line captions. "
        "Constraints: title <= 60 chars, caption <= 100 chars, no sensitive content. "
        "Return JSON: {\"items\":[{\"template\":\"A|B\",\"title\":\"...\",\"caption\":\"...\"}]}"
    )
    user = (
        f"PHRASE: {phrase}\\n"
        f"COUNT: {n}\\n"
        "Prefer style split: template A around 70%, template B around 30%."
    )
    payload = client.chat_json(system=system, user=user)

    items = []
    for item in payload.get("items", []):
        if not isinstance(item, dict):
            continue
        title = (item.get("title") or "").strip()
        caption = (item.get("caption") or "").strip()
        template = (item.get("template") or "A").strip().upper()
        if not title or not caption:
            continue
        if len(title) > 60 or len(caption) > 100:
            continue
        items.append({"template": template if template in {"A", "B"} else "A", "title": title, "caption": caption})

    return items[:n]


def generate_titles_basic(phrase: str, n: int = 3) -> list[dict]:
    seeds = [
        {
            "template": "A",
            "title": f"I tested {phrase} for 7 days",
            "caption": "This trend is everywhere right now.",
        },
        {
            "template": "A",
            "title": f"Everyone is trying {phrase}",
            "caption": "Would you try this trend too?",
        },
        {
            "template": "B",
            "title": f"How to use {phrase} in your next video",
            "caption": "Simple angle, better watch-time.",
        },
    ]
    return seeds[:n]
