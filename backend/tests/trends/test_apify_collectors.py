import pytest

from apps.trends.models import Platform
from apps.trends.services import apify_collectors


@pytest.mark.django_db
def test_instagram_collector_normalizes_schema(monkeypatch):
    payload = [
        {
            "id": "abc123",
            "caption": "street style ideas",
            "url": "https://www.instagram.com/p/abc123/",
            "likeCount": 1200,
            "commentsCount": 80,
        }
    ]

    monkeypatch.setattr(apify_collectors, "_run_actor", lambda *args, **kwargs: payload)

    items = apify_collectors.collect_instagram_from_apify(limit=10, region="US")
    assert len(items) == 1
    assert items[0]["platform"] == Platform.INSTAGRAM
    assert items[0]["external_id"] == "abc123"
    assert items[0]["source_url"] == "https://www.instagram.com/p/abc123/"
    assert "raw_metrics" in items[0]


@pytest.mark.django_db
def test_facebook_collector_normalizes_schema(monkeypatch):
    payload = [
        {
            "postId": "fb001",
            "text": "summer outfit trend",
            "url": "https://facebook.com/post/fb001",
            "reactions": 800,
            "comments": 42,
            "shares": 16,
        }
    ]

    monkeypatch.setattr(apify_collectors, "_run_actor", lambda *args, **kwargs: payload)

    items = apify_collectors.collect_facebook_from_apify(limit=10, region="US")
    assert len(items) == 1
    assert items[0]["platform"] == Platform.FACEBOOK
    assert items[0]["external_id"] == "fb001"
    assert items[0]["title_text"] == "summer outfit trend"
