from __future__ import annotations

import json
import os
import re
from typing import Any

import requests


_REHYDRATION_RE = re.compile(
    r"<script[^>]+id=[\"']__UNIVERSAL_DATA_FOR_REHYDRATION__[\"'][^>]*>(.*?)</script>",
    re.S | re.I,
)
_ITEM_ID_RE = re.compile(r"video/(\d+)")


def _extract_rehydration_json(html: str) -> dict[str, Any]:
    match = _REHYDRATION_RE.search(html or "")
    if not match:
        return {}
    raw = match.group(1).strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _pick_item_modules(payload: dict[str, Any]) -> list[dict[str, Any]]:
    candidate_roots = [
        payload.get("__DEFAULT_SCOPE__", {}),
        payload.get("default", {}),
        payload,
    ]
    for root in candidate_roots:
        item_module = (
            root.get("webapp.video-detail", {})
            .get("itemInfo", {})
            .get("itemStruct")
        )
        if item_module:
            return [item_module]

        item_map = (
            root.get("webapp.trending", {})
            .get("itemList", {})
            .get("itemList", [])
        )
        if item_map:
            return item_map

        item_module_map = root.get("ItemModule")
        if isinstance(item_module_map, dict) and item_module_map:
            return list(item_module_map.values())
    return []


def fetch_tiktok_trending(limit: int = 20, region: str = "US") -> list[dict[str, Any]]:
    base_url = os.getenv("TIKTOK_TRENDING_URL", "https://www.tiktok.com/trending")
    url = f"{base_url}?lang=en&region={region.lower()}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }

    response = requests.get(url, headers=headers, timeout=25)
    response.raise_for_status()

    payload = _extract_rehydration_json(response.text)
    modules = _pick_item_modules(payload)

    result: list[dict[str, Any]] = []
    for module in modules[: max(1, limit * 2)]:
        if not isinstance(module, dict):
            continue

        video_id = str(module.get("id") or "").strip()
        desc = (module.get("desc") or module.get("title") or "").strip()
        author = (module.get("author", {}).get("nickname") if isinstance(module.get("author"), dict) else "") or ""
        stats = module.get("stats") if isinstance(module.get("stats"), dict) else {}

        if not video_id:
            share_url = module.get("shareUrl") or module.get("video", {}).get("playAddr") or ""
            match = _ITEM_ID_RE.search(str(share_url))
            if match:
                video_id = match.group(1)

        if not video_id or not desc:
            continue

        source_url = f"https://www.tiktok.com/@{author}/video/{video_id}" if author else f"https://www.tiktok.com/video/{video_id}"

        result.append(
            {
                "external_id": video_id,
                "source_url": source_url,
                "title_text": desc,
                "caption_text": desc,
                "raw_metrics": {
                    "playCount": stats.get("playCount"),
                    "diggCount": stats.get("diggCount"),
                    "commentCount": stats.get("commentCount"),
                    "shareCount": stats.get("shareCount"),
                },
            }
        )

        if len(result) >= limit:
            break

    return result
