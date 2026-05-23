import pytest
from rest_framework.test import APIClient

from apps.trends.models import DigitalHumanSessionLog


@pytest.mark.django_db
def test_digital_human_chat_returns_required_fields():
    client = APIClient()

    response = client.post(
        "/api/digital-human/chat/",
        {"question": "这个热词值得做吗？", "platform": "tiktok"},
        format="json",
    )

    assert response.status_code == 200

    for field in ["answer", "highlights", "intent", "provider", "livetalking", "trace_id"]:
        assert field in response.data


@pytest.mark.django_db
def test_digital_human_chat_persists_session_log():
    client = APIClient()

    response = client.post(
        "/api/digital-human/chat/",
        {"question": "这个热词值得做吗？", "platform": "tiktok"},
        format="json",
    )

    assert response.status_code == 200
    trace_id = response.data["trace_id"]

    log = DigitalHumanSessionLog.objects.get(trace_id=trace_id)
    assert log.platform == "tiktok"
    assert log.question == "这个热词值得做吗？"
    assert bool(log.answer)
    assert log.provider in {"deepseek", "fallback"}
