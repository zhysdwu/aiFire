from __future__ import annotations

import os
from typing import Any

from apps.trends.models import Platform
from apps.trends.services.apify_client import ApifyClient


def _run_actor(actor_id: str, actor_input: dict[str, Any]) -> list[dict[str, Any]]:
    client = ApifyClient(token=os.getenv("APIFY_TOKEN", "").strip())
    return client.run_actor(actor_id=actor_id, actor_input=actor_input)


def _build_metrics(
    views: int = 0,
    likes: int = 0,
    comments: int = 0,
    shares: int = 0,
) -> dict[str, int]:
    return {
        "views": max(0, int(views or 0)),
        "diggCount": max(0, int(likes or 0)),
        "commentCount": max(0, int(comments or 0)),
        "shareCount": max(0, int(shares or 0)),
    }


def collect_tiktok_from_apify(limit: int = 50, region: str = "US") -> list[dict[str, Any]]:
    actor_id = os.getenv("APIFY_TIKTOK_ACTOR", "clockworks/tiktok-scraper")
    payload = _run_actor(actor_id, {"resultsPerPage": limit, "region": region})

    out: list[dict[str, Any]] = []
    for row in payload[:limit]:
        external_id = str(row.get("id") or row.get("aweme_id") or "").strip()
        if not external_id:
            continue
        caption = str(row.get("text") or row.get("desc") or "").strip()
        url = str(row.get("webVideoUrl") or row.get("url") or "").strip()
        stats = row.get("stats") or {}
        out.append(
            {
                "platform": Platform.TIKTOK,
                "region": region,
                "external_id": external_id,
                "source_url": url or f"https://www.tiktok.com/tag/{external_id}",
                "title_text": caption[:120],
                "caption_text": caption[:500],
                "raw_metrics": _build_metrics(
                    views=stats.get("playCount") or row.get("playCount"),
                    likes=stats.get("diggCount") or row.get("diggCount"),
                    comments=stats.get("commentCount") or row.get("commentCount"),
                    shares=stats.get("shareCount") or row.get("shareCount"),
                ),
            }
        )
    return out


def collect_instagram_from_apify(limit: int = 50, region: str = "US") -> list[dict[str, Any]]:
    actor_id = os.getenv("APIFY_INSTAGRAM_ACTOR", "apify/instagram-scraper")
    payload = _run_actor(
        actor_id,
        {
            "addParentData": False,
            "directUrls": ["https://www.instagram.com/humansofny/"],
            "resultsLimit": limit,
            "resultsType": "posts",
            "searchLimit": 10,
            "searchType": "hashtag",
        },
    )

    out: list[dict[str, Any]] = []
    for row in payload[:limit]:
        external_id = str(row.get("id") or row.get("shortCode") or "").strip()
        if not external_id:
            continue
        caption = str(row.get("caption") or row.get("text") or "").strip()
        url = str(row.get("url") or "").strip()
        out.append(
            {
                "platform": Platform.INSTAGRAM,
                "region": region,
                "external_id": external_id,
                "source_url": url or f"https://www.instagram.com/p/{external_id}/",
                "title_text": caption[:120],
                "caption_text": caption[:500],
                "raw_metrics": _build_metrics(
                    likes=row.get("likesCount") or row.get("likeCount"),
                    comments=row.get("commentsCount"),
                ),
            }
        )
    return out


def collect_facebook_from_apify(limit: int = 50, region: str = "US") -> list[dict[str, Any]]:
    actor_id = os.getenv("APIFY_FACEBOOK_ACTOR", "apify/facebook-posts-scraper")
    payload = _run_actor(
        actor_id,
        {
            "captionText": False,
            "resultsLimit": max(1, min(limit, 20)),
            "startUrls": [{"url": "https://www.facebook.com/humansofnewyork/"}],
        },
    )

    out: list[dict[str, Any]] = []
    for row in payload[:limit]:
        external_id = str(row.get("postId") or row.get("id") or "").strip()
        if not external_id:
            continue
        text = str(row.get("text") or row.get("message") or "").strip()
        url = str(row.get("url") or "").strip()
        out.append(
            {
                "platform": Platform.FACEBOOK,
                "region": region,
                "external_id": external_id,
                "source_url": url or f"https://www.facebook.com/{external_id}",
                "title_text": text[:120],
                "caption_text": text[:500],
                "raw_metrics": _build_metrics(
                    likes=row.get("reactionsCount") or row.get("reactions"),
                    comments=row.get("commentsCount") or row.get("comments"),
                    shares=row.get("sharesCount") or row.get("shares"),
                ),
            }
        )
    return out


def collect_youtube_from_apify(limit: int = 50, region: str = "US") -> list[dict[str, Any]]:
    actor_id = os.getenv("APIFY_YOUTUBE_ACTOR", "streamers/youtube-scraper")
    payload = _run_actor(
        actor_id,
        {
            "downloadSubtitles": False,
            "hasCC": False,
            "hasLocation": False,
            "hasSubtitles": False,
            "is360": False,
            "is3D": False,
            "is4K": False,
            "isBought": False,
            "isHD": False,
            "isHDR": False,
            "isLive": False,
            "isVR180": False,
            "maxResultStreams": 0,
            "maxResults": max(1, min(limit, 100)),
            "maxResultsShorts": 0,
            "preferAutoGeneratedSubtitles": False,
            "saveSubsToKVS": False,
            "searchQueries": [os.getenv("YOUTUBE_DEFAULT_QUERY", "Crawlee")],
        },
    )

    out: list[dict[str, Any]] = []
    for row in payload[:limit]:
        video_id = str(row.get("id") or row.get("videoId") or row.get("url") or "").strip()
        if not video_id:
            continue
        title = str(row.get("title") or row.get("name") or "").strip()
        caption = str(row.get("description") or row.get("text") or title).strip()
        url = str(row.get("url") or "").strip()
        out.append(
            {
                "platform": Platform.YOUTUBE,
                "region": region,
                "external_id": video_id[:120],
                "source_url": url or f"https://www.youtube.com/watch?v={video_id}",
                "title_text": title[:120],
                "caption_text": caption[:500],
                "raw_metrics": _build_metrics(
                    views=row.get("viewCount") or row.get("views"),
                    likes=row.get("likeCount") or row.get("likes"),
                    comments=row.get("commentCount") or row.get("commentsCount"),
                    shares=row.get("shareCount") or row.get("shares"),
                ),
            }
        )
    return out
