import pytest

from apps.trends.models import Platform
from apps.trends.services import source_collectors


@pytest.mark.django_db
def test_instagram_terms_falls_back_to_generic_trends(monkeypatch):
    monkeypatch.setattr(source_collectors, "collect_instagram_from_apify", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        source_collectors,
        "fetch_google_trends_terms",
        lambda *args, **kwargs: [
            {
                "platform": Platform.GOOGLE_TRENDS,
                "region": "US",
                "external_id": "gtrends-1",
                "source_url": "https://trends.google.com/trending?geo=US",
                "title_text": "quiet luxury",
                "caption_text": "quiet luxury",
                "raw_metrics": {"views": 1000, "diggCount": 100, "commentCount": 10, "shareCount": 5},
            }
        ],
    )

    items = source_collectors.fetch_instagram_terms(limit=10, region="US")

    assert items
    assert items[0]["platform"] == Platform.INSTAGRAM
    assert items[0]["title_text"] == "quiet luxury"


@pytest.mark.django_db
def test_facebook_terms_falls_back_to_generic_trends(monkeypatch):
    monkeypatch.setattr(source_collectors, "collect_facebook_from_apify", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        source_collectors,
        "fetch_google_trends_terms",
        lambda *args, **kwargs: [
            {
                "platform": Platform.GOOGLE_TRENDS,
                "region": "US",
                "external_id": "gtrends-2",
                "source_url": "https://trends.google.com/trending?geo=US",
                "title_text": "product review",
                "caption_text": "product review",
                "raw_metrics": {"views": 1000, "diggCount": 100, "commentCount": 10, "shareCount": 5},
            }
        ],
    )

    items = source_collectors.fetch_facebook_terms(limit=10, region="US")

    assert items
    assert items[0]["platform"] == Platform.FACEBOOK
    assert items[0]["title_text"] == "product review"


@pytest.mark.django_db
def test_youtube_terms_falls_back_to_generic_trends(monkeypatch):
    monkeypatch.setattr(source_collectors, "collect_youtube_from_apify", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        source_collectors,
        "fetch_google_trends_terms",
        lambda *args, **kwargs: [
            {
                "platform": Platform.GOOGLE_TRENDS,
                "region": "US",
                "external_id": "gtrends-3",
                "source_url": "https://trends.google.com/trending?geo=US",
                "title_text": "youtube growth tips",
                "caption_text": "youtube growth tips",
                "raw_metrics": {"views": 1000, "diggCount": 100, "commentCount": 10, "shareCount": 5},
            }
        ],
    )

    items = source_collectors.fetch_youtube_terms(limit=10, region="US")

    assert items
    assert items[0]["platform"] == Platform.YOUTUBE
    assert items[0]["title_text"] == "youtube growth tips"
