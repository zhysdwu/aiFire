from __future__ import annotations

import csv
import io
import os
import re
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from urllib.parse import quote

import requests

from apps.trends.models import Platform

_HASHTAG_RE = re.compile(r"#([A-Za-z][A-Za-z0-9_]{1,50})")
_TERM_RE = re.compile(r"[A-Za-z][A-Za-z0-9' -]{2,80}")


def _normalize_term(text: str) -> str:
    text = (text or "").strip().lower()
    text = text.replace("_", " ").replace("-", " ")
    text = re.sub(r"\s+", " ", text)
    return text


def _dedupe_keep_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        value = _normalize_term(item)
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def fetch_tiktok_creative_center_hashtags(limit: int = 50, region: str = "US") -> list[dict]:
    urls = [
        "https://ads.tiktok.com/business/creativecenter/inspiration/popular/hashtag/pc/en",
        "https://ads.tiktok.com/business/creativecenter/inspiration/popular/hashtag/pad/en",
    ]
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }

    hashtags: list[str] = []
    for url in urls:
        response = requests.get(url, headers=headers, timeout=25)
        response.raise_for_status()
        hashtags.extend(_HASHTAG_RE.findall(response.text))
        if len(hashtags) >= limit:
            break

    terms = _dedupe_keep_order(hashtags)[:limit]
    result: list[dict] = []
    for idx, term in enumerate(terms, start=1):
        tag = term.replace(" ", "")
        score = max(1, limit - idx + 1)
        result.append(
            {
                "platform": Platform.TIKTOK,
                "region": region,
                "external_id": f"ttcc-{tag}",
                "source_url": (
                    "https://ads.tiktok.com/business/creativecenter/hashtag/"
                    f"{quote(tag)}/pc/en"
                ),
                "title_text": tag,
                "caption_text": f"tiktok hashtag trend {tag}",
                "raw_metrics": {
                    "views": score * 20000,
                    "diggCount": score * 900,
                    "commentCount": score * 120,
                    "shareCount": score * 40,
                },
            }
        )
    return result


def fetch_google_trends_terms(limit: int = 50, geo: str = "US") -> list[dict]:
    urls = [
        f"https://trends.google.com/trends/trendingsearches/daily/rss?geo={geo}",
        f"https://trends.google.com/trending/rss?geo={geo}",
    ]
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }

    xml_text = ""
    for url in urls:
        try:
            resp = requests.get(url, headers=headers, timeout=25)
            resp.raise_for_status()
            if "xml" in (resp.headers.get("Content-Type") or "").lower() or resp.text.lstrip().startswith("<rss"):
                xml_text = resp.text
                break
        except Exception:
            continue

    if not xml_text:
        return []

    root = ET.fromstring(xml_text)
    titles = [node.text or "" for node in root.findall(".//item/title")]
    terms = _dedupe_keep_order(titles)[:limit]

    result: list[dict] = []
    for idx, term in enumerate(terms, start=1):
        score = max(1, limit - idx + 1)
        key = re.sub(r"[^a-z0-9]+", "-", term.lower()).strip("-")
        result.append(
            {
                "platform": Platform.GOOGLE_TRENDS,
                "region": geo,
                "external_id": f"gtrends-{key or idx}",
                "source_url": f"https://trends.google.com/trending?geo={geo}",
                "title_text": term,
                "caption_text": term,
                "raw_metrics": {
                    "views": score * 15000,
                    "diggCount": score * 600,
                    "commentCount": score * 80,
                    "shareCount": score * 20,
                },
            }
        )
    return result


def fetch_answer_the_public_terms_from_csv(limit: int = 50, csv_path: str | None = None) -> list[dict]:
    path = csv_path or os.getenv("ANSWER_THE_PUBLIC_CSV", "")
    if not path or not os.path.exists(path):
        return []

    with open(path, "r", encoding="utf-8-sig") as f:
        raw = f.read()
    reader = csv.DictReader(io.StringIO(raw))

    candidates: list[str] = []
    preferred_fields = ["Keyword", "keyword", "Question", "question", "Search Term", "Term", "term"]

    for row in reader:
        value = ""
        for field in preferred_fields:
            value = (row.get(field) or "").strip()
            if value:
                break
        if not value:
            for cell in row.values():
                value = (cell or "").strip()
                if value:
                    break
        if not value:
            continue
        match = _TERM_RE.search(value)
        if match:
            candidates.append(match.group(0))

    terms = _dedupe_keep_order(candidates)[:limit]
    result: list[dict] = []
    for idx, term in enumerate(terms, start=1):
        score = max(1, limit - idx + 1)
        key = re.sub(r"[^a-z0-9]+", "-", term.lower()).strip("-")
        result.append(
            {
                "platform": Platform.ANSWER_THE_PUBLIC,
                "region": "US",
                "external_id": f"atp-{key or idx}",
                "source_url": "https://answerthepublic.com/",
                "title_text": term,
                "caption_text": term,
                "raw_metrics": {
                    "views": score * 12000,
                    "diggCount": score * 500,
                    "commentCount": score * 70,
                    "shareCount": score * 15,
                },
            }
        )
    return result
